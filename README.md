# Gossip

A modern **Python** desktop application built with **GTK4 / Libadwaita** to explore, inspect, and manage the complete lifecycle of secrets across multiple cloud providers and local environments:

- 🔵 **Google Cloud Platform (Secret Manager)**
- 🟠 **Amazon Web Services (AWS Secrets Manager)**
- 🔷 **Microsoft Azure (Key Vault)**
- 🔴 **Ansible Vault (AES-256 Encrypted YAML files)**
- 🟡 **AWS Systems Manager Parameter Store**
- ⚫ **HashiCorp Vault / OpenBao (KV v2)**
- 🟣 **Kubernetes Secrets**

> **Why "Gossip"?** A nod to *Gossip Girl*, the series (2007–2012) about an anonymous blogger who knew everyone's secrets and could not keep quiet. This application also lives among secrets, but it never tells: values stay hidden until you reveal them and never reach logs or the state file.

Developed on **NixOS** and configured with **devenv** and **uv**.

---

## Key Features

- ☁️ **True Multi-Cloud Provider Support (GCP, AWS Secrets Manager, AWS Parameter Store, Azure, Ansible Vault, HashiCorp Vault / OpenBao, Kubernetes)**: Switch seamlessly in real-time between Google Cloud Platform, Amazon Web Services, Microsoft Azure, Ansible Vault, and HashiCorp Vault / OpenBao using the dropdown selector in the HeaderBar without restarting the application.
- 🔍 **Intelligent Context Auto-Detection**:
  - **GCP**: Automatically detects the active project via `gcloud`, environment variables (`GOOGLE_CLOUD_PROJECT`), or Application Default Credentials (ADC).
  - **AWS**: Automatically detects the active profile (`~/.aws/credentials`, `~/.aws/config`, `AWS_PROFILE`) and region (`AWS_REGION` or `us-east-1`).
  - **Azure**: Automatically detects the active vault from environment variables (`AZURE_KEYVAULT_NAME`, `AZURE_VAULT_URL`) or via Azure CLI discovery (`az keyvault list`).
  - **Ansible Vault**: Discovers vault files within the current workspace (`vault.yml`, `group_vars/all/vault.yml`, `secrets.yml`), environment variables (`ANSIBLE_VAULT_FILE`, `ANSIBLE_VAULT_PASSWORD_FILE`). The password is never read from the environment. Password files are never guessed from the workspace: use `--ansible-password-file` or `ANSIBLE_VAULT_PASSWORD_FILE`, and the file must be private (`chmod 600`) or Gossip ignores it.
  - **AWS Parameter Store**: Uses the same profile and region as AWS Secrets Manager (`gossip -P ssm`).
  - **HashiCorp Vault / OpenBao**: Reads the server from `VAULT_ADDR`/`BAO_ADDR` (or `--vault-addr`), the token from `VAULT_TOKEN`/`BAO_TOKEN` or `~/.vault-token`, and works with KV v2 mounts (`--vault-mount`). Plain HTTP is refused except on localhost.
  - **Kubernetes**: Reads contexts from `KUBECONFIG` or `~/.kube/config` (`--kube-context`, `--kube-namespace`); supports token, certificate and `exec` plugin authentication and always verifies the cluster certificate.
- 🔒 **Read-only mode and audit trail**: the lock button in the header bar (or `gossip --read-only` / `GOSSIP_READ_ONLY=1` to start in that mode) hides and blocks creating, editing, deleting and importing, which is handy for production. `gossip --audit-log [FILE]` (or `GOSSIP_AUDIT_LOG`) appends one JSON line per reveal, copy, create, change, delete, import and export to a private local file (`audit.jsonl` next to the saved state by default). It records secret names and counts, never values.
- 🛠️ **Everyday tools**: restore an older version as the current one, edit labels and descriptions, view a multi-key value as a table and copy a single key, generate random passwords, preview imports (and add new versions to existing secrets), compare a secret with one from another environment or provider, a collapsible tree for names with `/` in a virtualized list, a stale-secret flag (`--stale-days`), keyboard shortcuts (`F1`) and a redacted diagnostics report in the About window.
- 🛡️ **Safer by default**: copied secrets are marked so clipboard managers do not keep them, secrets are hidden when the screen locks or the computer suspends (Linux/BSD), and the dependency pins are audited weekly with a CycloneDX SBOM attached to each release.
- 🧠 **Remembers your last context**: the provider and its project, profile, vault file, server or namespace are restored on the next launch (command-line options win, then the saved choice, then autodetection). Passwords, tokens and keys are never saved. The file is `state.json` in your configuration folder (`~/.config/gossip`, `~/Library/Application Support/gossip` or `%APPDATA%\gossip`); delete it to forget everything.
- 🔄 **Interactive Context Configuration Dialogs**:
  - **GCP**: Searchable modal dialog to browse and select available Google Cloud projects.
  - **AWS**: Modal dialog to configure credentials profile and AWS region.
  - **Azure**: Modal dialog to enter a Key Vault identifier or select from discovered vaults.
  - **Ansible Vault**: Modal dialog with file browser, automatic workspace vault detection, and secure password / password-file unlocking with instant validation.
- 🌐 **Full Internationalization (i18n)**: Native gettext catalog support (`.po` / `.mo`). Supports English (`en`) and Spanish (`es`) with auto-detection or manual selection. Includes an automatic pure-Python PO-to-MO compiler.
- 🎨 **Native GTK4 + Libadwaita Interface**: Modern GNOME design standards with native light/dark mode support, smooth micro-animations, and responsive adaptive layouts.
- ⚡ **Asynchronous Non-Blocking Operations**: All network and encryption operations run on worker threads, keeping the user interface smooth and responsive at 60 FPS.
- 👁️ **Secure Value Masking**: Secret payloads remain masked by default (`••••••••`), with instant toggle to reveal or hide the raw payload or SecretString.
- 📋 **Clipboard Integration**: One-click copying of secret values, versions, identifiers, ARNs, and vault resource URIs with visual in-app feedback toasts.
- 📜 **Version History & Lifecycle Management**:
  - **GCP & Azure**: View versions with `ENABLED` and `DISABLED` states, and toggle individual versions on or off.
  - **AWS**: Inspect versions and their rotation staging labels (`AWSCURRENT`, `AWSPREVIOUS`).
  - **Ansible Vault**: Key management with automatic backup files (`.bak`) generated on edits.
- ➕ **Version Management (Payload Updates)**: Add new versions and payloads to existing secrets across all providers.
- 🗑️ **Safe Deletion**: Dialogs with destructive confirmation styling to delete secrets or Ansible Vault variables permanently.
- ➕ **Secret Creation**: Create brand new secrets directly from the sidebar with custom IDs, initial payloads, labels/tags, and optional descriptions.
- 🔎 **Real-Time Instant Search**: Live filter secrets by name, description, or labels/tags, with `label:key=value` and `-word` operators and a `Ctrl+F` (`Cmd+F` on macOS) shortcut.
- 🔀 **Version Diff**: Compare any two versions of a secret as a unified diff (JSON-aware).
- 📦 **Import / Export**: Back up or migrate secrets as JSON; values are opt-in and existing secrets are never overwritten.
- ⏱️ **Inactivity Lock**: Hides and forgets revealed secrets and wipes the clipboard after 5 idle minutes (configurable).
- 🛡️ **Tested**: Automated test suite (370+ tests, about 98% coverage) with a CI gate that fails below 95% coverage.

---

## Prerequisites & Authentication

### 1. NixOS & devenv
The project includes a ready-to-use `devenv.nix` configured with GTK4, Libadwaita, GObject Introspection, `uv`, and Python 3.14.

**Just want to use it on Nix/NixOS?** The repository is also a flake: `nix run github:sincorchetes/gossip`, or add it to your configuration as described in [docs/getting-started/installation.md](docs/getting-started/installation.md#2-nix-nixos-devenv).

### 2. Google Cloud Platform (GCP)
```bash
gcloud auth application-default login
```

### 3. Amazon Web Services (AWS)
```bash
aws configure
# Or using AWS IAM Identity Center (SSO):
aws sso login
```
Or export the standard environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION`.

### 4. Microsoft Azure (Key Vault)
```bash
az login
```
Or export service principal credentials: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID`.

### 5. Ansible Vault
Compatible with any YAML file encrypted via `ansible-vault` (AES-256). You can supply the password directly in the graphical unlock dialog or reference a password file explicitly (`--ansible-password-file` or `ANSIBLE_VAULT_PASSWORD_FILE`). Files readable by other users are ignored; run `chmod 600` on them.

---

### 6. Environment variables
Every variable Gossip and each provider read (project, profile, region, vault, token, kubeconfig, proxies, Flatpak) is listed in [docs/environment.md](docs/environment.md).

## Quickstart with devenv

Enter the repository directory:

```bash
# Launch devenv shell (automatically initializes uv and dependencies)
devenv shell
```

### Running the Graphical Application (GUI)

From within the devenv environment:
```bash
# Using the configured script shortcut:
gossip

# Or executing the Python entrypoint directly:
python src/main.py
```

### Command-Line Arguments (CLI)

```bash
# Launch with Ansible Vault and a specific vault file:
gossip -P ansible --ansible-vault ./vault.yml

# Browse production safely and keep a local audit trail:
gossip --read-only --audit-log

# Launch with Azure Key Vault specifying the vault name:
gossip -P azure --azure-vault my-keyvault

# Launch with a HashiCorp Vault / OpenBao server and KV v2 mount:
gossip -P vault --vault-addr https://vault.example.com:8200 --vault-mount secret

# Launch with a Kubernetes context and namespace:
gossip -P k8s --kube-context my-cluster --kube-namespace apps

# Launch directly into AWS Secrets Manager:
gossip -P aws --aws-profile production --aws-region us-east-1

# Launch in GCP with a specific project ID:
gossip -P gcp -p my-gcp-project-12345

# Select interface language (English or Spanish):
gossip --lang en
gossip --lang es

# Start maximized or specify initial window dimensions:
gossip --maximized
gossip --width 1440 --height 900
```

---

## Testing & Quality Assurance

Gossip enforces high code quality standards through an extensive automated test suite:

```bash
# Run the complete test suite with coverage report:
devenv test

# Or run pytest directly inside devenv shell:
pytest
```

- **Coverage**: about 98% of statements and branches (see `htmlcov/index.html` after a run).
- **Enforced Threshold**: the pipeline fails if total coverage falls below **95%** (`--cov-fail-under=95` in `pyproject.toml`).
- **Reports**: Generates terminal summary, `coverage.xml` (Cobertura format), and HTML report in `htmlcov/index.html`.

---

## CI/CD Pipeline (GitHub Actions)

The workflows live in `.github/workflows/`:

- **`ci.yml`** – on every push and pull request: the full test suite with the coverage gate, run through `devenv` (Python 3.14).
- **`release.yml`** – on every `v*` tag it builds, smoke-tests (`gossip --self-test`) and publishes:
  - **Linux**: `.deb`, `.rpm` and a portable tarball for `x86_64` and `aarch64`, plus a Flatpak bundle (GNOME 51 runtime).
  - **Windows**: MSI installer (`gossip-windows-x64.msi`) and portable archive (`gossip-windows-x64.zip`), both bundling GTK4 runtime DLLs.
  - **macOS**: disk images bundling `gossip.app`, one per architecture: `gossip-macos-arm64.dmg` (Apple Silicon) and `gossip-macos-x86_64.dmg` (Intel).
  - `SHA256SUMS.txt` and a build-provenance attestation for every release.
- **`pages.yml`** – publishes this documentation to GitHub Pages.
- **`update-build-deps.yml`** – weekly pull request refreshing the pinned, hashed dependencies (`requirements.txt` for development, `requirements-build.txt` for releases).

See [docs/cicd.md](docs/cicd.md) for details.

---

## Project Structure

```
gossip-gcp/
├── .github/workflows/  # CI, release, docs and dependency-refresh workflows
├── devenv.nix          # NixOS environment configuration (GTK4, Libadwaita, uv, gettext)
├── devenv.yaml         # devenv metadata
├── requirements.in     # Runtime, test and docs dependencies (edit this)
├── requirements.txt    # Same, pinned with hashes (generated by uv)
├── AUTHORS.md          # Project authors and contribution credits
├── LICENSE.md          # GNU General Public License v3.0 or later
├── THIRD_PARTY_NOTICES.md # Licenses and credits of bundled third-party software (generated)
├── README.md           # Project documentation
├── pyproject.toml      # Project metadata, pytest and coverage gate (fail-under: 95%)
├── locales/            # Internationalization catalogs (.po / .mo)
│   ├── en/LC_MESSAGES/gossip-gcp.po
│   └── es/LC_MESSAGES/gossip-gcp.po
└── src/
    ├── __init__.py
    ├── exceptions.py    # Typed domain exceptions for secret providers
    ├── i18n.py          # i18n manager and automatic pure-Python PO-to-MO compiler
    ├── main.py          # CLI entry point and argument parsing
    ├── models.py        # Strongly-typed Dataclasses for secrets, versions, and contexts
    ├── providers/       # Polymorphic secret provider strategies (Clean Architecture)
    │   ├── __init__.py  # Public provider exports
    │   ├── base.py      # BaseSecretProvider (abstract Strategy Pattern contract)
    │   ├── gcp.py       # GCPSecretClient (Google Cloud Platform Secret Manager)
    │   ├── aws.py       # AWSSecretClient (Amazon Web Services Secrets Manager)
    │   ├── azure.py     # AzureSecretClient (Microsoft Azure Key Vault)
    │   ├── ansible.py   # AnsibleVaultClient (Ansible Vault AES-256 encrypted YAML)
    │   └── vault/       # VaultClient (HashiCorp Vault / OpenBao KV v2)
    └── ui/
        ├── __init__.py
        ├── app.py       # Adw.Application and theme CSS management
        ├── window.py    # Main window (HeaderBar, provider switcher, sidebar, viewer)
        └── dialogs/     # Decoupled dialog modules (Single Responsibility Principle)
            ├── __init__.py
            ├── about.py   # About application dialog
            ├── project.py # Google Cloud project selector dialog
            ├── aws.py     # AWS profile and region selector dialog
            ├── azure.py   # Azure Key Vault selector dialog
            ├── ansible.py # Ansible Vault selector and unlock dialog
            ├── secret.py  # Secret creation and version payload addition dialogs
            └── confirm.py # Destructive action confirmation dialogs
```

---

## Authors & Credits

Gossip is developed and maintained by [Álvaro Castillo](https://github.com/sincorchetes) ([sincorchetes.tech](https://sincorchetes.tech)), who directs the project, defines the architecture and reviews and validates every change. Copyright © 2026 Álvaro Castillo.

Most of the code was written with an AI coding assistant working under that direction: [Claude](https://www.anthropic.com) is credited as **collaborator**, not as copyright holder. See [AUTHORS.md](AUTHORS.md) for details.

---

## License

Gossip is free software licensed under the **GNU General Public License, version 3 or (at your option) any later version (GPL-3.0-or-later)**. See [LICENSE.md](LICENSE.md) for the complete terms.

Gossip is built on, and its packages bundle, third-party software distributed under its own licenses (GTK, libadwaita, PyGObject, boto3, the Google and Azure SDKs, Ansible Core and others). Their names, versions, licenses and license texts are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), which every package also ships and the *About* dialog links to. Libraries under the LGPL are shipped as separate shared libraries so they can be replaced by your own builds.
