"""Discovery and Azure CLI integration for Key Vaults."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import List, Optional

from src.models import AzureVaultItem


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
) -> List[AzureVaultItem]:
    """List accessible Azure Key Vaults discovered via Azure CLI.

    Args:
        current_vault: Optional currently configured vault name.
        current_vault_url: Optional currently configured vault URL.

    Returns:
        List[AzureVaultItem]: List of discovered vault items.
    """
    vaults: List[AzureVaultItem] = []
    try:
        cmd = "az.cmd" if sys.platform == "win32" else "az"
        res = subprocess.run(
            [
                cmd,
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
            shell=(sys.platform == "win32"),
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            for item in data:
                name = item.get("name", "")
                uri = item.get("vaultUri", f"https://{name}.vault.azure.net/")
                loc = item.get("location")
                if name:
                    vaults.append(AzureVaultItem(name=name, vault_uri=uri, location=loc))
    except Exception:
        pass

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
