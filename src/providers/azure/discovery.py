"""Discovery and Azure CLI integration for Key Vaults."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import List, Optional

from src.log import get_logger
from src.models import AzureVaultItem

log = get_logger(__name__)


def detect_vault_name() -> Optional[str]:
    """Detect active Azure Key Vault name from environment variables.

    Returns:
        Optional[str]: Detected vault identifier or None.
    """
    for var in ("AZURE_KEYVAULT_NAME", "AZURE_VAULT_NAME", "AZURE_VAULT_URL", "KEYVAULT_NAME"):
        val = os.getenv(var)
        if val and val.strip():
            clean = val.strip()
            if "vault.azure.net" in clean:
                clean = clean.replace("https://", "").replace("http://", "").split(".")[0]
            return clean
    return None


def list_available_vaults(
    current_vault: Optional[str] = None,
    current_vault_url: Optional[str] = None,
    problems: Optional[List[str]] = None,
) -> List[AzureVaultItem]:
    """List accessible Azure Key Vaults discovered via Azure CLI.

    Args:
        current_vault: Optional currently configured vault name.
        current_vault_url: Optional currently configured vault URL.
        problems: Optional list that receives a human-readable reason when discovery fails.

    Returns:
        List[AzureVaultItem]: List of discovered vault items.
    """
    vaults: List[AzureVaultItem] = []
    try:
        # which() resolves az.cmd on Windows (PATHEXT), so no shell is needed
        az = shutil.which("az") or "az"
        res = subprocess.run(
            [
                az,
                "keyvault",
                "list",
                "--query",
                "[].{name: name, vaultUri: properties.vaultUri, location: location}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            for item in data:
                name = item.get("name", "")
                uri = item.get("vaultUri", f"https://{name}.vault.azure.net/")
                loc = item.get("location")
                if name:
                    vaults.append(AzureVaultItem(name=name, vault_uri=uri, location=loc))
        elif res.returncode != 0 and problems is not None:
            problems.append(res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "az")
    except Exception as exc:
        log.debug("az keyvault list failed", exc_info=True)
        if problems is not None:
            problems.append(str(exc))

    if current_vault and not any(v.name.lower() == current_vault.lower() for v in vaults):
        vaults.insert(
            0,
            AzureVaultItem(
                name=current_vault,
                vault_uri=current_vault_url or f"https://{current_vault}.vault.azure.net/",
            ),
        )

    vaults.sort(key=lambda v: v.name.lower())
    return vaults
