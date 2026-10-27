# HashiCorp Vault / OpenBao Provider

Implementation of `BaseSecretProvider` for [HashiCorp Vault](https://www.vaultproject.io/) and [OpenBao](https://openbao.org/) servers using the **KV version 2** secrets engine. It talks to the HTTP API with the Python standard library, so it adds no dependency.

## Connecting

| Setting | Dialog field | Environment | CLI |
| :--- | :--- | :--- | :--- |
| Server address | Server address | `VAULT_ADDR` / `BAO_ADDR` | `--vault-addr` |
| KV v2 mount (default `secret`) | KV v2 mount | | `--vault-mount` |
| Namespace | Namespace | `VAULT_NAMESPACE` / `BAO_NAMESPACE` | |
| Token | Token | `VAULT_TOKEN` / `BAO_TOKEN`, then `~/.vault-token` | |
| Custom CA bundle | | `VAULT_CACERT` / `BAO_CACERT` | |

- The token typed in the dialog lives in memory only and is dropped when the idle lock engages.
- The token is sent in a header, so `http://` addresses are refused except for `localhost`. Certificate verification cannot be disabled.

## How secrets map to the interface

- Secrets are listed recursively (up to 8 folders deep and 5000 secrets); the secret name is its path, e.g. `app/prod/db`.
- A KV secret is a map of keys. A JSON object typed in the editor is stored as several keys; any other text is stored under the key `value` and shown back as plain text.
- Every write creates a new version. Previous versions can be read, compared, disabled (soft delete, reversible) and permanently destroyed.
- Creating a secret never overwrites an existing one (check-and-set).
- Deleting a secret removes its metadata and all versions.

::: src.providers.vault.VaultClient
    options:
      show_root_heading: true
      show_source: true
