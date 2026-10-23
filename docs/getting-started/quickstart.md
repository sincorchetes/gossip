# Quickstart & Provider Configuration

Learn how to authenticate with each supported secret backend, configure environments, and use the command-line options.

---

## Provider Authentication Setup

Gossip connects directly to cloud APIs and local files using standard credentials. Configure your preferred provider before or during execution.

### 1. Google Cloud Platform (GCP Secret Manager)

Gossip uses Google Application Default Credentials (ADC) to authenticate against the Secret Manager API:

1. **Log in with the Google Cloud CLI:**
   ```bash
   gcloud auth application-default login
   ```
2. **Set your active project:**
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```
   *Alternatively, configure a service account key file:*
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
   ```
3. **Required IAM Permissions:**
   * `roles/secretmanager.secretAccessor` (read secret values)
   * `roles/secretmanager.viewer` (list secrets and versions)
   * `roles/secretmanager.admin` (create, delete, and manage secrets)

> [!TIP]
> You can switch between active GCP projects directly in Gossip using the project switcher button in the header bar.

---

### 2. Amazon Web Services (AWS Secrets Manager)

Gossip integrates with the standard AWS credential chain:

1. **Configure credentials using AWS CLI:**
   ```bash
   aws configure
   ```
   *Or supply environment variables:*
   ```bash
   export AWS_ACCESS_KEY_ID="AKIA..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_DEFAULT_REGION="eu-west-1"
   ```
2. **Named Profiles:**
   Gossip supports custom profiles defined in `~/.aws/credentials` and `~/.aws/config`:
   ```bash
   gossip --provider aws --aws-profile production --aws-region us-east-1
   ```
3. **Required IAM Policies:**
   * `secretsmanager:ListSecrets`
   * `secretsmanager:DescribeSecret`
   * `secretsmanager:GetSecretValue`
   * `secretsmanager:CreateSecret`, `secretsmanager:PutSecretValue`, `secretsmanager:DeleteSecret`

---

### 3. Microsoft Azure Key Vault

Gossip authenticates with Azure Key Vault using `DefaultAzureCredential`:

1. **Sign in via Azure CLI:**
   ```bash
   az login
   ```
   *Or configure Service Principal environment variables:*
   ```bash
   export AZURE_CLIENT_ID="..."
   export AZURE_CLIENT_SECRET="..."
   export AZURE_TENANT_ID="..."
   ```
2. **Specify your Key Vault name:**
   Set the vault name via environment variable or in Gossip's dialog:
   ```bash
   export AZURE_KEYVAULT_NAME="my-production-vault"
   ```
3. **Required Azure RBAC Roles:**
   * `Key Vault Secrets User` (read secrets)
   * `Key Vault Secrets Officer` (create, update, enable/disable, and delete secrets)

---

### 4. Ansible Vault (Local Files)

Gossip allows exploring, updating, and adding variables to encrypted Ansible Vault YAML files locally:

1. **Supported File Conventions:**
   Gossip automatically discovers:
   * `vault.yml`, `vault.yaml`
   * `group_vars/all/vault.yml`, `group_vars/all/vault.yaml`
   * `vars/vault.yml`, `secrets.yml`, `.vault.yml`
   * Any file starting with the `$ANSIBLE_VAULT` signature.
2. **Password Configuration:**
   * Supply the vault password interactively in Gossip's unlock modal.
   * Or point to a password file: `.vault_pass` in the project root or `~/.vault_pass`.
   * Or use environment variables:
     ```bash
     export ANSIBLE_VAULT_PASSWORD_FILE="/path/to/.vault_pass"
     export ANSIBLE_VAULT_PASSWORD="mySecretPassword"
     ```

---

## Command Line Interface (CLI)

Gossip provides flexible CLI arguments to pre-select providers, dimensions, and settings:

```bash
gossip [OPTIONS]
```

### Options Reference

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--provider` | Active provider (`gcp`, `aws`, `azure`, `ansible`) | `--provider aws` |
| `--gcp-project` | GCP Project ID | `--gcp-project my-app-prod` |
| `--aws-profile` | Named AWS credentials profile | `--aws-profile prod-team` |
| `--aws-region` | Target AWS region name | `--aws-region us-east-1` |
| `--azure-vault` | Azure Key Vault name or DNS URL | `--azure-vault prod-keyvault` |
| `--ansible-vault` | Path to Ansible Vault file | `--ansible-vault ./vault.yml` |
| `--ansible-password` | Plaintext password to unlock Ansible Vault | `--ansible-password secret` |
| `--ansible-password-file` | Path to password file (`.vault_pass`) | `--ansible-password-file ./.pass` |
| `--lang` | Initial application language (`en` or `es`) | `--lang en` |
| `--maximized` | Start window in maximized state | `--maximized` |
| `--width` | Custom window width in pixels (min: 900) | `--width 1440` |
| `--height` | Custom window height in pixels (min: 600) | `--height 900` |
| `--version` | Show Gossip version and exit | `--version` |
| `--help` | Display command help and exit | `--help` |
