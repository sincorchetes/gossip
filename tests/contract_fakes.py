"""In-memory stand-ins for every backend, used by the provider contract tests."""

from __future__ import annotations

import itertools
import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from botocore.exceptions import ClientError
from google.api_core.exceptions import AlreadyExists, NotFound, PermissionDenied

from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    GCPSecretClient,
    KubernetesClient,
    SSMClient,
    VaultClient,
)
from src.providers.kubernetes.api import KubeAPIError
from src.providers.vault.api import VaultAPIError

_clock = itertools.count()


def now() -> datetime:
    """Strictly increasing timestamps, so newest-first sorting is deterministic."""
    return datetime(2026, 1, 1) + timedelta(seconds=next(_clock))


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Op")


class Harness:
    """What the contract tests need from one provider."""

    provider_id = ""
    supports_denial = True

    def make(self) -> Any:
        raise NotImplementedError

    def deny(self) -> None:
        """Make every following call fail as if the credentials lacked permission."""
        raise NotImplementedError

    def cleanup(self) -> None:
        """Release anything created by make()."""


# --------------------------------------------------------------------------- GCP
class FakeGCP:
    def __init__(self):
        self.secrets: Dict[str, List[bytes]] = {}
        self.labels: Dict[str, Dict[str, str]] = {}
        self.denied = False

    def _check(self):
        if self.denied:
            raise PermissionDenied("denied")

    def _secret(self, name):
        return SimpleNamespace(
            name=name,
            create_time=None,
            labels=dict(self.labels.get(name, {})),
            replication=SimpleNamespace(automatic=True, user_managed=None),
        )

    @staticmethod
    def _version(parent, number):
        return SimpleNamespace(
            name=f"{parent}/versions/{number}", state=1, create_time=None, destroy_time=None
        )

    def create_secret(self, request):
        self._check()
        name = f"{request['parent']}/secrets/{request['secret_id']}"
        if name in self.secrets:
            raise AlreadyExists("already exists")
        self.secrets[name] = []
        self.labels[name] = dict(request["secret"].get("labels") or {})
        return self._secret(name)

    def update_secret(self, request):
        self._check()
        name = request["secret"]["name"]
        if name not in self.secrets:
            raise NotFound("missing")
        self.labels[name] = dict(request["secret"]["labels"])

    def add_secret_version(self, request):
        self._check()
        parent = request["parent"]
        if parent not in self.secrets:
            raise NotFound("missing")
        self.secrets[parent].append(request["payload"]["data"])
        return self._version(parent, len(self.secrets[parent]))

    def list_secrets(self, request):
        self._check()
        return [self._secret(n) for n in self.secrets]

    def list_secret_versions(self, request):
        self._check()
        if request.parent not in self.secrets:
            raise NotFound("missing")
        return [
            self._version(request.parent, i + 1) for i in range(len(self.secrets[request.parent]))
        ]

    def access_secret_version(self, request):
        self._check()
        parent, _, number = request.name.partition("/versions/")
        if parent not in self.secrets or not self.secrets[parent]:
            raise NotFound("missing")
        index = len(self.secrets[parent]) if number == "latest" else int(number)
        return SimpleNamespace(payload=SimpleNamespace(data=self.secrets[parent][index - 1]))

    def delete_secret(self, request):
        self._check()
        if request["name"] not in self.secrets:
            raise NotFound("missing")
        del self.secrets[request["name"]]


class GcpHarness(Harness):
    provider_id = "gcp"

    def make(self):
        self.fake = FakeGCP()
        provider = GCPSecretClient(project_id="proj")
        provider.initialize_client = lambda: self.fake  # type: ignore[method-assign]
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- AWS
class _Paginator:
    def __init__(self, pages: Callable[..., List[dict]]):
        self._pages = pages

    def paginate(self, **kwargs):
        return self._pages(**kwargs)


class FakeSecretsManager:
    ARN = "arn:aws:secretsmanager:eu-west-1:1:secret:"

    def __init__(self):
        self.secrets: Dict[str, List[str]] = {}
        self.tags: Dict[str, Dict[str, str]] = {}
        self.descriptions: Dict[str, Optional[str]] = {}
        self.denied = False

    def _tag_list(self, name):
        return [{"Key": k, "Value": v} for k, v in self.tags.get(name, {}).items()]

    def _name(self, secret_id: str) -> str:
        name = secret_id[len(self.ARN) :] if secret_id.startswith(self.ARN) else secret_id
        if self.denied:
            raise client_error("AccessDeniedException")
        if name not in self.secrets:
            raise client_error("ResourceNotFoundException")
        return name

    def get_paginator(self, _operation):
        def pages(**_kwargs):
            if self.denied:
                raise client_error("AccessDeniedException")
            entries = [
                {
                    "ARN": self.ARN + n,
                    "Name": n,
                    "Description": self.descriptions.get(n),
                    "Tags": self._tag_list(n),
                }
                for n in self.secrets
            ]
            return [{"SecretList": entries}]

        return _Paginator(pages)

    def create_secret(self, Name, SecretString=None, Tags=(), Description=None, **_kw):
        if self.denied:
            raise client_error("AccessDeniedException")
        if Name in self.secrets:
            raise client_error("ResourceExistsException")
        self.secrets[Name] = [] if SecretString is None else [SecretString]
        self.tags[Name] = {t["Key"]: t["Value"] for t in Tags}
        if Description:
            self.descriptions[Name] = Description
        return {"ARN": self.ARN + Name, "Name": Name}

    def describe_secret(self, SecretId):
        name = self._name(SecretId)
        return {"Name": name, "Tags": self._tag_list(name)}

    def update_secret(self, SecretId, Description=None, **_kw):
        self.descriptions[self._name(SecretId)] = Description

    def tag_resource(self, SecretId, Tags):
        self.tags[self._name(SecretId)].update({t["Key"]: t["Value"] for t in Tags})

    def untag_resource(self, SecretId, TagKeys):
        for key in TagKeys:
            self.tags[self._name(SecretId)].pop(key, None)

    def put_secret_value(self, SecretId, SecretString):
        self.secrets[self._name(SecretId)].append(SecretString)
        return {"VersionId": str(len(self.secrets[self._name(SecretId)])), "VersionStages": []}

    def get_secret_value(self, SecretId, VersionId=None, **_kw):
        values = self.secrets[self._name(SecretId)]
        if not values:
            raise client_error("ResourceNotFoundException")
        index = int(VersionId) if VersionId else len(values)
        return {"SecretString": values[index - 1], "VersionId": str(index)}

    def list_secret_version_ids(self, SecretId, **_kw):
        values = self.secrets[self._name(SecretId)]
        return {
            "Versions": [
                {
                    "VersionId": str(i + 1),
                    "VersionStages": ["AWSCURRENT"] if i + 1 == len(values) else [],
                    "CreatedDate": now(),
                }
                for i in range(len(values))
            ]
        }

    def delete_secret(self, SecretId, **_kw):
        del self.secrets[self._name(SecretId)]


class AwsHarness(Harness):
    provider_id = "aws"

    def make(self):
        self.fake = FakeSecretsManager()
        provider = AWSSecretClient(profile_name="p", region_name="eu-west-1")
        provider._client = self.fake
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- SSM
class FakeSSM:
    def __init__(self):
        self.parameters: Dict[str, Dict[str, Any]] = {}
        self.denied = False

    def _check(self):
        if self.denied:
            raise client_error("AccessDeniedException")

    def put_parameter(self, Name, Value, Type="String", Overwrite=False, Tags=(), **_kw):
        self._check()
        if Name in self.parameters and not Overwrite:
            raise client_error("ParameterAlreadyExists")
        entry = self.parameters.setdefault(Name, {"Type": Type, "versions": [], "tags": {}})
        entry["tags"].update({t["Key"]: t["Value"] for t in Tags})
        entry["versions"].append(Value)
        return {"Version": len(entry["versions"])}

    def get_parameter(self, Name, WithDecryption=True):
        self._check()
        name, _, number = Name.partition(":")
        if name not in self.parameters:
            raise client_error("ParameterNotFound")
        entry = self.parameters[name]
        index = int(number) if number else len(entry["versions"])
        if index > len(entry["versions"]):
            raise client_error("ParameterVersionNotFound")
        return {
            "Parameter": {
                "Name": name,
                "Type": entry["Type"],
                "Value": entry["versions"][index - 1],
            }
        }

    def get_paginator(self, operation):
        def describe(**_kw):
            self._check()
            return [
                {"Parameters": [{"Name": n, "Type": e["Type"]} for n, e in self.parameters.items()]}
            ]

        def history(Name, **_kw):
            self._check()
            if Name not in self.parameters:
                raise client_error("ParameterNotFound")
            count = len(self.parameters[Name]["versions"])
            return [
                {
                    "Parameters": [
                        {"Version": i + 1, "Labels": [], "LastModifiedDate": now()}
                        for i in range(count)
                    ]
                }
            ]

        return _Paginator(describe if operation == "describe_parameters" else history)

    def list_tags_for_resource(self, ResourceType, ResourceId):
        self._check()
        tags = self.parameters[ResourceId]["tags"]
        return {"TagList": [{"Key": k, "Value": v} for k, v in tags.items()]}

    def add_tags_to_resource(self, ResourceType, ResourceId, Tags):
        self.parameters[ResourceId]["tags"].update({t["Key"]: t["Value"] for t in Tags})

    def remove_tags_from_resource(self, ResourceType, ResourceId, TagKeys):
        for key in TagKeys:
            self.parameters[ResourceId]["tags"].pop(key, None)

    def delete_parameter(self, Name):
        self._check()
        if Name not in self.parameters:
            raise client_error("ParameterNotFound")
        del self.parameters[Name]


class SsmHarness(Harness):
    provider_id = "ssm"

    def make(self):
        self.fake = FakeSSM()
        provider = SSMClient(profile_name="p", region_name="eu-west-1")
        provider._client = self.fake
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- Azure
class FakeKeyVault:
    def __init__(self):
        self.secrets: Dict[str, List[str]] = {}
        self.properties: Dict[str, Dict[str, Any]] = {}
        self.denied = False

    def _check(self):
        if self.denied:
            error = HttpResponseError(message="denied")
            error.status_code = 403
            raise error

    def set_secret(self, name, value, tags=None, content_type=None):
        self._check()
        self.secrets.setdefault(name, []).append(value)
        self.properties.setdefault(name, {"tags": {}, "content_type": None})
        if tags:
            self.properties[name]["tags"] = dict(tags)
        if content_type:
            self.properties[name]["content_type"] = content_type
        number = str(len(self.secrets[name]))
        return SimpleNamespace(
            id=f"https://kv/secrets/{name}/{number}", properties=SimpleNamespace(version=number)
        )

    def get_secret(self, name, version=None):
        self._check()
        if name not in self.secrets:
            raise ResourceNotFoundError("missing")
        values = self.secrets[name]
        index = int(version) if version else len(values)
        return SimpleNamespace(value=values[index - 1])

    def list_properties_of_secrets(self):
        self._check()
        return [
            SimpleNamespace(
                name=n,
                id=f"https://kv/secrets/{n}",
                content_type=self.properties[n]["content_type"],
                created_on=now(),
                updated_on=now(),
                tags=dict(self.properties[n]["tags"]),
                enabled=True,
            )
            for n in self.secrets
        ]

    def list_properties_of_secret_versions(self, name):
        self._check()
        if name not in self.secrets:
            raise ResourceNotFoundError("missing")
        return [
            SimpleNamespace(version=str(i + 1), created_on=now(), enabled=True)
            for i in range(len(self.secrets[name]))
        ]

    def update_secret_properties(self, name, tags=None, content_type=None, **_kw):
        self._check()
        if name not in self.secrets:
            raise ResourceNotFoundError("missing")
        self.properties[name] = {"tags": dict(tags or {}), "content_type": content_type}

    def begin_delete_secret(self, name):
        self._check()
        if name not in self.secrets:
            raise ResourceNotFoundError("missing")
        del self.secrets[name]


class AzureHarness(Harness):
    provider_id = "azure"

    def make(self):
        self.fake = FakeKeyVault()
        provider = AzureSecretClient(vault_name="kv")
        provider._client = self.fake
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- Vault / OpenBao
class FakeVault:
    def __init__(self):
        self.secrets: Dict[str, List[Dict[str, Any]]] = {}
        self.custom: Dict[str, Dict[str, str]] = {}
        self.denied = False

    def request(self, method, path, body=None, query=None):
        if self.denied:
            raise VaultAPIError(403, ["permission denied"])
        parts = path.split("/", 2)
        kind, name = parts[1], (parts[2] if len(parts) > 2 else "")
        if kind == "metadata" and method == "GET" and query:
            return {"data": {"keys": sorted(self.secrets)}} if name == "" else self._missing()
        if kind == "metadata" and method == "GET":
            if name not in self.secrets:
                raise VaultAPIError(404, [])
            versions = {
                str(i + 1): {"created_time": "2026-01-01T00:00:00Z"}
                for i in range(len(self.secrets[name]))
            }
            custom = self.custom.get(name) or None
            return {"data": {"versions": versions, "custom_metadata": custom}}
        if kind == "metadata" and method == "POST":
            if name not in self.secrets:
                raise VaultAPIError(404, [])
            self.custom[name] = dict(body["custom_metadata"])
            return None
        if kind == "metadata" and method == "DELETE":
            self.secrets.pop(name, None)
            return None
        if kind == "data" and method == "GET":
            if name not in self.secrets:
                raise VaultAPIError(404, [])
            number = int((query or {}).get("version", len(self.secrets[name])))
            return {"data": {"data": self.secrets[name][number - 1]}}
        if kind == "data" and method == "POST":
            if (body.get("options") or {}).get("cas") == 0 and name in self.secrets:
                raise VaultAPIError(400, ["check-and-set parameter did not match"])
            self.secrets.setdefault(name, []).append(body["data"])
            return {"data": {"version": len(self.secrets[name])}}
        raise AssertionError(f"unexpected {method} {path}")

    @staticmethod
    def _missing():
        raise VaultAPIError(404, [])


class VaultHarness(Harness):
    provider_id = "vault"

    def make(self):
        self.fake = FakeVault()
        provider = VaultClient(address="https://v", mount="secret")
        provider._http_client = self.fake
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- Kubernetes
class FakeKube:
    def __init__(self):
        self.secrets: Dict[str, Dict[str, Any]] = {}
        self.denied = False
        self._version = itertools.count(1)

    def request(self, method, path, body=None, query=None):
        if self.denied:
            raise KubeAPIError(403, "forbidden")
        name = "" if path.endswith("/secrets") else path.rsplit("/", 1)[1]
        if method == "GET" and not name:
            return {"items": list(self.secrets.values()), "metadata": {}}
        if method == "GET":
            if name not in self.secrets:
                raise KubeAPIError(404, "not found")
            return self.secrets[name]
        if method == "POST":
            new = body["metadata"]["name"]
            if new in self.secrets:
                raise KubeAPIError(409, f'secrets "{new}" already exists')
            self.secrets[new] = self._store(body)
            return self.secrets[new]
        if method == "PUT":
            self.secrets[name] = self._store(body)
            return self.secrets[name]
        if method == "DELETE":
            if name not in self.secrets:
                raise KubeAPIError(404, "not found")
            del self.secrets[name]
            return {}
        raise AssertionError(f"unexpected {method} {path}")

    def _store(self, body):
        meta = {**body["metadata"], "resourceVersion": str(next(self._version))}
        return {**body, "metadata": meta}


class KubernetesHarness(Harness):
    provider_id = "k8s"

    def make(self):
        self.fake = FakeKube()
        provider = KubernetesClient(context="c", namespace="ns")
        provider._http_client = self.fake
        return provider

    def deny(self):
        self.fake.denied = True


# --------------------------------------------------------------------------- Ansible Vault
class AnsibleHarness(Harness):
    provider_id = "ansible"
    supports_denial = False

    def make(self):
        self.folder = tempfile.TemporaryDirectory()
        path = os.path.join(self.folder.name, "vault.yml")
        provider = AnsibleVaultClient(vault_file=path, password="contract-password")
        provider.create_new_vault_file(path, "contract-password")
        return provider

    def cleanup(self):
        self.folder.cleanup()


HARNESSES: List[type] = [
    GcpHarness,
    AwsHarness,
    SsmHarness,
    AzureHarness,
    VaultHarness,
    KubernetesHarness,
    AnsibleHarness,
]
