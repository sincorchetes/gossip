"""Project discovery and Cloud Resource Manager integrations for GCP."""

from __future__ import annotations

import configparser
import os
from typing import Any, List, Optional

import google.auth

from src.i18n import _
from src.log import get_logger
from src.models import GCPProjectItem

log = get_logger(__name__)


def detect_project_id() -> Optional[str]:
    """Detect the active GCP project from environment variables, gcloud config files, or ADC.

    Returns:
        Optional[str]: Detected GCP project identifier or None if undetected.
    """
    for env_var in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT"):
        val = os.getenv(env_var)
        if val and val.strip():
            return val.strip()

    try:
        config_dir = os.path.expanduser("~/.config/gcloud")
        active_config_path = os.path.join(config_dir, "active_config")
        config_name = "default"
        if os.path.exists(active_config_path):
            with open(active_config_path, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c:
                    config_name = c

        config_file = os.path.join(config_dir, "configurations", f"config_{config_name}")
        if os.path.exists(config_file):
            parser = configparser.ConfigParser()
            parser.read(config_file)
            if parser.has_option("core", "project"):
                proj = parser.get("core", "project").strip()
                if proj:
                    return proj
    except Exception:
        log.debug("gcloud config project lookup failed", exc_info=True)

    try:
        _, project = google.auth.default()
        if project and project.strip():
            return project.strip()
    except Exception:
        log.debug("google.auth.default project lookup failed", exc_info=True)

    return None


def fetch_available_projects(credentials: Any) -> List[GCPProjectItem]:
    """Lists active GCP projects accessible to the authenticated credentials.

    Args:
        credentials: Valid Google Auth credentials instance.

    Returns:
        List[GCPProjectItem]: Discovered accessible GCP projects.
    """
    from google.auth.transport.requests import AuthorizedSession

    session = AuthorizedSession(credentials)
    url: Optional[str] = "https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=300"
    projects: List[GCPProjectItem] = []

    try:
        while url:
            resp = session.get(url, timeout=12)
            if resp.status_code != 200:
                raise RuntimeError(
                    _("Error {status} while querying projects: {detail}").format(
                        status=resp.status_code, detail=resp.text
                    )
                )

            data = resp.json()
            for p in data.get("projects", []):
                if p.get("lifecycleState") == "ACTIVE" or not p.get("lifecycleState"):
                    p_id = p.get("projectId", "")
                    p_name = p.get("name", p_id)
                    projects.append(
                        GCPProjectItem(
                            project_id=p_id,
                            name=p_name,
                            lifecycle_state=p.get("lifecycleState", "ACTIVE"),
                        )
                    )

            next_token = data.get("nextPageToken")
            if next_token:
                url = f"https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=300&pageToken={next_token}"
            else:
                url = None

        projects.sort(key=lambda p: p.project_id.lower())
        return projects
    except Exception as exc:
        raise RuntimeError(f"{_('Could not query GCP projects')}: {exc}") from exc
