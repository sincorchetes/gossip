"""Reading kubeconfig files and turning a context into connection settings."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml

from src.i18n import _
from src.log import get_logger

log = get_logger(__name__)

EXEC_TIMEOUT = 30
DEFAULT_NAMESPACE = "default"


@dataclass
class ClusterAccess:
    """Everything needed to talk to one cluster as one user.

    Attributes:
        server: API server URL.
        ca_pem: PEM text of the cluster CA, or None to use the system trust store.
        token: Bearer token, if the user authenticates with one.
        cert_pem: PEM client certificate, if any.
        key_pem: PEM client key, if any.
        namespace: Default namespace of the context.
    """

    server: str
    ca_pem: Optional[str] = None
    token: Optional[str] = None
    cert_pem: Optional[str] = None
    key_pem: Optional[str] = None
    namespace: str = DEFAULT_NAMESPACE


def kubeconfig_paths() -> List[str]:
    """Files named by KUBECONFIG (path-separated) or the default ``~/.kube/config``."""
    env = os.getenv("KUBECONFIG", "").strip()
    if env:
        return [p for p in env.split(os.pathsep) if p]
    return [os.path.join(os.path.expanduser("~"), ".kube", "config")]


def load_kubeconfig() -> Dict[str, Any]:
    """Merge the kubeconfig files like kubectl: the first file defining a name wins."""
    merged: Dict[str, Any] = {"clusters": {}, "users": {}, "contexts": {}, "current-context": None}
    for path in kubeconfig_paths():
        try:
            with open(path, encoding="utf-8") as handle:
                doc = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError):
            log.debug("could not read kubeconfig %s", path, exc_info=True)
            continue
        if not isinstance(doc, dict):
            continue
        for kind in ("clusters", "users", "contexts"):
            for entry in doc.get(kind) or []:
                if isinstance(entry, dict) and entry.get("name"):
                    merged[kind].setdefault(entry["name"], entry)
        merged["current-context"] = merged["current-context"] or doc.get("current-context")
    return merged


def list_contexts() -> List[str]:
    """Names of the contexts defined in the kubeconfig files."""
    return sorted(load_kubeconfig()["contexts"])


def current_context() -> Optional[str]:
    """The kubeconfig's current context, or the only context when there is just one."""
    config = load_kubeconfig()
    if config["current-context"]:
        return config["current-context"]
    names = list(config["contexts"])
    return names[0] if len(names) == 1 else None


def context_namespace(name: Optional[str]) -> str:
    """Default namespace declared by a context, or "default"."""
    context = load_kubeconfig()["contexts"].get(name or "") or {}
    return (context.get("context") or {}).get("namespace") or DEFAULT_NAMESPACE


def _read_text(path: str) -> str:
    with open(os.path.expanduser(path), encoding="utf-8") as handle:
        return handle.read().strip()


def _decode(data: Optional[str]) -> Optional[str]:
    return base64.b64decode(data).decode("utf-8") if data else None


def _exec_credentials(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Run a client-go credential plugin (aws eks, gke-gcloud-auth-plugin, ...)."""
    env = dict(os.environ)
    for item in spec.get("env") or []:
        env[item["name"]] = item.get("value", "")
    command = [spec["command"], *(spec.get("args") or [])]
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=EXEC_TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            _("The credential plugin '{command}' could not run: {detail}").format(
                command=spec["command"], detail=exc
            )
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            _("The credential plugin '{command}' failed: {detail}").format(
                command=spec["command"], detail=result.stderr.strip() or result.returncode
            )
        )
    try:
        return json.loads(result.stdout).get("status") or {}
    except ValueError as exc:
        raise RuntimeError(
            _("The credential plugin '{command}' returned invalid output.").format(
                command=spec["command"]
            )
        ) from exc


def resolve_context(name: Optional[str]) -> ClusterAccess:
    """Build the connection settings of a context.

    Args:
        name: Context name; the kubeconfig's current context when omitted.

    Raises:
        ValueError: If the context or its cluster does not exist or is not supported.
        RuntimeError: If a credential plugin fails.
    """
    config = load_kubeconfig()
    name = name or current_context()
    context = config["contexts"].get(name or "")
    if not context:
        raise ValueError(
            _(
                "No Kubernetes context selected.\n"
                "Use the context button to choose one from your kubeconfig."
            )
        )
    ctx = context.get("context") or {}
    cluster = (config["clusters"].get(ctx.get("cluster")) or {}).get("cluster") or {}
    user = (config["users"].get(ctx.get("user")) or {}).get("user") or {}
    if not cluster.get("server"):
        raise ValueError(
            _("The context '{name}' does not point to a cluster with a server.").format(name=name)
        )
    if cluster.get("insecure-skip-tls-verify"):
        raise ValueError(
            _(
                "The context '{name}' disables TLS verification, which Gossip does not allow. "
                "Add the cluster's certificate-authority instead."
            ).format(name=name)
        )
    if user.get("auth-provider") or user.get("username"):
        raise ValueError(
            _(
                "The context '{name}' uses a legacy authentication method that is not supported."
            ).format(name=name)
        )

    access = ClusterAccess(
        server=cluster["server"].rstrip("/"),
        namespace=ctx.get("namespace") or DEFAULT_NAMESPACE,
    )
    if cluster.get("certificate-authority-data"):
        access.ca_pem = _decode(cluster["certificate-authority-data"])
    elif cluster.get("certificate-authority"):
        access.ca_pem = _read_text(cluster["certificate-authority"])

    access.token = user.get("token")
    if not access.token and user.get("tokenFile"):
        access.token = _read_text(user["tokenFile"])
    if user.get("client-certificate-data"):
        access.cert_pem = _decode(user["client-certificate-data"])
        access.key_pem = _decode(user.get("client-key-data"))
    elif user.get("client-certificate"):
        access.cert_pem = _read_text(user["client-certificate"])
        access.key_pem = _read_text(user["client-key"]) if user.get("client-key") else None
    if user.get("exec"):
        status = _exec_credentials(user["exec"])
        access.token = status.get("token") or access.token
        access.cert_pem = status.get("clientCertificateData") or access.cert_pem
        access.key_pem = status.get("clientKeyData") or access.key_pem
    return access
