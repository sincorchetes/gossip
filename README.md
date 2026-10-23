# Gossip

A modern **Python** desktop application built with **GTK4 / Libadwaita** to explore, inspect, and manage the complete lifecycle of secrets across multiple cloud providers and local environments:

- 🔵 **Google Cloud Platform (Secret Manager)**
- 🟠 **Amazon Web Services (AWS Secrets Manager)**
- 🔷 **Microsoft Azure (Key Vault)**
- 🔴 **Ansible Vault (AES-256 Encrypted YAML files)**

Developed on **NixOS** and configured with **devenv** and **uv**.

---

## Key Features

- ☁️ **True Multi-Cloud Provider Support (GCP, AWS, Azure, Ansible Vault)**: Switch seamlessly in real-time between Google Cloud Platform, Amazon Web Services, Microsoft Azure, and Ansible Vault using the dropdown selector in the HeaderBar without restarting the application.
- 🔍 **Intelligent Context Auto-Detection**:
  - **GCP**: Automatically detects the active project via `gcloud`, environment variables (`GOOGLE_CLOUD_PROJECT`), or Application Default Credentials (ADC).
  - **AWS**: Automatically detects the active profile (`~/.aws/credentials`, `~/.aws/config`, `AWS_PROFILE`) and region (`AWS_REGION` or `us-east-1`).
  - **Azure**: Automatically detects the active vault from environment variables (`AZURE_KEYVAULT_NAME`, `AZURE_VAULT_URL`) or via Azure CLI discovery (`az keyvault list`).
  - **Ansible Vault**: Discovers vault files within the current workspace (`vault.yml`, `group_vars/all/vault.yml`, `secrets.yml`), environment variables (`ANSIBLE_VAULT_FILE`, `ANSIBLE_VAULT_PASSWORD`, `ANSIBLE_VAULT_PASSWORD_FILE`), and `.vault_pass` files.
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
- 🔎 **Real-Time Instant Search**: Live filter secrets by name, description, or labels/tags.
- 🛡️ **100% Test Coverage**: Comprehensive test suite with 100% statement and branch coverage across all modules.

---

## Prerequisites & Authentication

### 1. NixOS & devenv
The project includes a ready-to-use `devenv.nix` configured with GTK4, Libadwaita, GObject Introspection, `uv`, and Python 3.13.

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
Compatible with any YAML file encrypted via `ansible-vault` (AES-256). You can supply the password directly in the graphical unlock dialog or reference a `.vault_pass` file.

---

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

# Launch with Azure Key Vault specifying the vault name:
gossip -P azure --azure-vault my-keyvault

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

- **Statements Coverage**: 100.00%
- **Branches Coverage**: 100.00%
- **Enforced Threshold**: The pipeline automatically fails if total code coverage falls below **90%** (`--cov-fail-under=90`).
- **Reports**: Generates terminal summary, `coverage.xml` (Cobertura format), and HTML report in `htmlcov/index.html`.

---

## CI/CD Pipeline (GitLab)

The repository includes a production-grade GitLab CI/CD configuration ([.gitlab-ci.yml](file:///.gitlab-ci.yml)):

- **Development Lifecycle (`dev -> pre -> release`)**:
  - `dev`: Continuous integration on active feature branches and Merge Requests (linter, unit tests, strict 90% coverage gate).
  - `pre`: Pre-production / Release Candidate stabilization stage verifying packaging and builds.
  - `release` / `main`: Tagged releases (`v*.*.*`) trigger the automated build and publication stages.
- **Multi-Platform Packaging**:
  - **Linux**: Self-contained portable tarball (`gossip-linux-x86_64.tar.gz`).
  - **Windows**: Portable distribution archive (`gossip-windows-x64.zip`) bundling GTK4 runtime DLLs.
  - **macOS**: Native disk image (`gossip-macos-universal.dmg`) bundling `gossip.app`.
- **Automated GitLab Releases**:
  - Artifacts are uploaded directly to the **GitLab Generic Package Registry** using `release-cli`, publishing release notes and download links on the project's Releases page.

---

## Project Structure

```
gossip-gcp/
├── .gitlab-ci.yml      # GitLab CI/CD pipeline (test gate, multi-platform build, release)
├── devenv.nix          # NixOS environment configuration (GTK4, Libadwaita, uv, gettext)
├── devenv.yaml         # devenv metadata
├── requirements.txt    # Python runtime and test dependencies
├── AUTHORS.md          # Project authors and contribution credits
├── LICENSE.md          # GNU General Public License v2.0
├── README.md           # Project documentation
├── pytest.ini          # Pytest and coverage gate configuration (fail-under: 90%)
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
    │   └── ansible.py   # AnsibleVaultClient (Ansible Vault AES-256 encrypted YAML)
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

This software was developed in a collaborative pair-programming model:

- **Code Authorship & Technical Implementation**: [Antigravity](https://deepmind.google) (Google DeepMind - Advanced Agentic Coding).
- **Project Direction, Product Architecture & Validation**: [sincorchetes.tech](https://sincorchetes.tech).

Please see [AUTHORS.md](file:///home/sincorchetes/Documents/gossip-gcp/AUTHORS.md) for full details.

---

## License

This project is licensed under the **GNU General Public License v2.0 (GPLv2)**. See the [LICENSE.md](file:///home/sincorchetes/Documents/gossip-gcp/LICENSE.md) file for complete terms and conditions.
