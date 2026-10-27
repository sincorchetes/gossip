# Ansible Vault Provider

Implementation of `BaseSecretProvider` for local Ansible Vault encrypted YAML files using `ansible-vault` and `PyYAML`.

## Behavior notes

- **Version history keeps the last 5 saves.** A vault file has no native history. Before each save Gossip rotates backups next to the vault: `<vault>.bak` (the state before the last save), `<vault>.bak.2`, ... up to `<vault>.bak.5`; older ones are discarded. The version list shows *Current* plus *Previous* and *Backup 2*-*5* for the backups in which the variable already existed. Keep the vault under version control (for example git) if you need a longer history.
- **Value types.** Dictionaries and lists are kept as structured YAML; scalars are read as text. A payload that looks like JSON (`{...}` or `[...]`) is stored as a structure. Export files carry dictionaries, lists, numbers and booleans as native JSON values, and importing restores their type.
- **Passwords.** The password is typed in the unlock dialog or read from a private password file you declare (`--ansible-password-file` or `ANSIBLE_VAULT_PASSWORD_FILE`). It is never read from the environment, and it is dropped from memory when the inactivity lock fires.

::: src.providers.ansible.AnsibleVaultClient
    options:
      show_root_heading: true
      show_source: true
