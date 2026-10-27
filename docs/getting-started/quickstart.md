# Quickstart & Provider Configuration

Learn how to authenticate with each supported secret backend, configure environments, and use the command-line options.

---

## Provider Authentication Setup

Gossip connects directly to the provider APIs and local files using standard credentials. Configure the provider you need before launching, or change its context from the header bar once Gossip is running.

### 1. Google Cloud Platform (GCP Secret Manager)

Gossip uses Google Application Default Credentials (ADC):

1. **Log in with the Google Cloud CLI:**
   ```bash
   gcloud auth application-default login
   ```
2. **Set your active project:**
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```
   *Alternatively, use a service account key file:*
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
   ```
3. **Required IAM permissions:**
   * `roles/secretmanager.secretAccessor` (read secret values)
   * `roles/secretmanager.viewer` (list secrets and versions)
   * `roles/secretmanager.admin` (create, delete, and manage secrets)

---

### 2. Amazon Web Services (AWS Secrets Manager)

Gossip uses the standard AWS credential chain:

1. **Configure credentials:**
   ```bash
   aws configure
   ```
   *Or supply environment variables:*
   ```bash
   export AWS_ACCESS_KEY_ID="AKIA..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_DEFAULT_REGION="eu-west-1"
   ```
2. **Named profiles** from `~/.aws/credentials` and `~/.aws/config`:
   ```bash
   gossip --provider aws --aws-profile production --aws-region us-east-1
   ```
3. **Required IAM actions:**
   * `secretsmanager:ListSecrets`, `DescribeSecret`, `GetSecretValue`, `ListSecretVersionIds`
   * `CreateSecret`, `PutSecretValue`, `DeleteSecret` to change data

> [!NOTE]
> Deleting a secret schedules it for deletion with a **7-day recovery window**. The delete dialog has a checkbox to delete immediately. Binary secrets are shown as `base64:<data>` and saved back as bytes.

---

### 3. AWS Systems Manager Parameter Store

Uses the same profile, region and credentials as Secrets Manager:

```bash
gossip --provider ssm --aws-profile production --aws-region eu-west-1
```

* Parameters are listed with their full path (`/app/prod/db`) and type.
* New parameters are created as encrypted `SecureString`. Editing keeps the type and creates a new version; the history shows labels.
* **Required IAM actions:** `ssm:DescribeParameters`, `ssm:GetParameter`, `ssm:GetParameterHistory`, `ssm:PutParameter`, `ssm:DeleteParameter` (and `kms:Decrypt` for custom keys).

---

### 4. Microsoft Azure Key Vault

Gossip authenticates with `DefaultAzureCredential`:

1. **Sign in:**
   ```bash
   az login
   ```
   *Or use Service Principal variables:*
   ```bash
   export AZURE_CLIENT_ID="..."
   export AZURE_CLIENT_SECRET="..."
   export AZURE_TENANT_ID="..."
   ```
2. **Choose the vault** in Gossip's dialog (the vaults found by the Azure CLI are listed, or you are told why they could not be), with `--azure-vault`, or through the environment:
   ```bash
   export AZURE_KEYVAULT_NAME="my-production-vault"
   ```
3. **Required RBAC roles:** `Key Vault Secrets User` (read) and `Key Vault Secrets Officer` (create, update, enable/disable and delete).

---

### 5. Ansible Vault (local files)

Explore, update and add variables of encrypted Ansible Vault YAML files:

1. **Discovered files:** `vault.yml`, `vault.yaml`, `group_vars/all/vault.yml`, `vars/vault.yml`, `secrets.yml`, `.vault.yml`, and any file starting with the `$ANSIBLE_VAULT` signature.
2. **Password:**
   * Type it in Gossip's unlock dialog (asked again after the inactivity lock), or
   * point to a password file with `--ansible-password-file` or:
     ```bash
     export ANSIBLE_VAULT_PASSWORD_FILE="/path/to/.vault_pass"
     ```
     The file must be private (`chmod 600`); Gossip ignores password files readable by other users and never searches for them. The password is not read from environment variables.
3. **History:** every save keeps the last five generations as backups next to the file (`.bak`, `.bak.2` … `.bak.5`).

---

### 6. HashiCorp Vault and OpenBao

Both are supported through the **KV version 2** secrets engine:

```bash
export VAULT_ADDR="https://vault.example.com:8200"   # or BAO_ADDR
vault login                                          # writes ~/.vault-token
gossip --provider vault --vault-mount secret
```

* **Token**: `VAULT_TOKEN` / `BAO_TOKEN`, then `~/.vault-token`, or type it in the server dialog (kept in memory only and dropped on inactivity lock).
* **Namespace** with `VAULT_NAMESPACE` / `BAO_NAMESPACE`; **custom CA** with `VAULT_CACERT` / `BAO_CACERT`.
* `http://` is only accepted for `localhost`; certificates are always verified.
* A JSON object is stored as several keys, other text under the key `value`. Versions can be disabled (soft-delete), re-enabled and destroyed.
* **Policy** needs `read`, `list`, `create`, `update` and `delete` on `<mount>/data/*` and `<mount>/metadata/*`, plus `update` on `<mount>/delete/*`, `<mount>/undelete/*` and `<mount>/destroy/*` for version actions.

---

### 7. Kubernetes Secrets

Gossip reads your kubeconfig (`KUBECONFIG`, or `~/.kube/config`) and manages the Secrets of one namespace:

```bash
gossip --provider k8s --kube-context my-cluster --kube-namespace apps
```

* The dialog lists your contexts and the namespaces of the chosen cluster (type the name if you may not list namespaces).
* Authentication: token, client certificate or `exec` credential plugins (EKS, GKE, AKS, OIDC). Contexts with `insecure-skip-tls-verify` and legacy `auth-provider` or basic authentication are refused.
* A JSON object of strings becomes several keys; binary values appear as `base64:<data>`. Editing keeps the Secret's type and labels. Each Secret has one version.
* **RBAC** needs `get`, `list`, `create`, `update` and `delete` on `secrets` in the namespace.

---

## Remembered context

Gossip remembers the last provider and context (project, profile and region, vault, Ansible file path, server and mount, kube context and namespace) and restores them next time. Precedence: **command line**, then **saved choice**, then autodetection. Passwords and tokens are never saved. See [Security & Privacy](../security.md).

---

## Command Line Interface (CLI)

```bash
gossip [OPTIONS]
```

### Providers and contexts

| Argument | Description | Example |
| :--- | :--- | :--- |
| `-P`, `--provider` | Initial provider: `gcp`, `aws`, `ssm`, `azure`, `ansible`, `vault`, `k8s` (default: the last one used, otherwise `gcp`) | `--provider vault` |
| `-p`, `--project` | GCP project ID | `--project my-app-prod` |
| `--aws-profile` | AWS credentials profile (AWS and Parameter Store) | `--aws-profile prod-team` |
| `--aws-region` | AWS region (AWS and Parameter Store) | `--aws-region us-east-1` |
| `--azure-vault` | Azure Key Vault name or URL | `--azure-vault prod-keyvault` |
| `--ansible-vault` | Path to the Ansible Vault file | `--ansible-vault ./vault.yml` |
| `--ansible-password-file` | Password file (must be `chmod 600`) | `--ansible-password-file ./.pass` |
| `--vault-addr` | HashiCorp Vault / OpenBao server URL (default: `VAULT_ADDR`) | `--vault-addr https://vault.example.com:8200` |
| `--vault-mount` | KV v2 mount path (default: `secret`) | `--vault-mount kv` |
| `--kube-context` | Kubeconfig context (default: the current one) | `--kube-context prod` |
| `--kube-namespace` | Namespace whose Secrets to manage | `--kube-namespace apps` |

### Safety and diagnostics

| Argument | Description |
| :--- | :--- |
| `--read-only` | Browse and copy only; locked for the whole session (also `GOSSIP_READ_ONLY=1`, which can be toggled) |
| `--audit-log [FILE]` | Record what is revealed, copied and changed (never values). Also `GOSSIP_AUDIT_LOG` |
| `--stale-days DAYS` | Flag secrets not changed for this many days (default 90; `0` disables). Also `GOSSIP_STALE_DAYS` |
| `--idle-lock SECONDS` | Inactivity lock delay (default 300; `0` disables). Also `GOSSIP_IDLE_LOCK_SECONDS` |
| `--debug` | Detailed diagnostics on stderr (also `GOSSIP_DEBUG=1`) |
| `--self-test` | Check that every dependency loads and exit |

### Window and language

| Argument | Description |
| :--- | :--- |
| `-l`, `--lang` | Interface language: `en` or `es` |
| `-m`, `--maximized` | Start maximized |
| `--width`, `--height` | Initial window size in pixels (default: the last size used, otherwise 1280 × 820) |
| `--renderer` | GTK renderer: `ngl`, `gl`, `vulkan`, `cairo` |
| `--software-rendering` | Force Cairo rendering (virtual machines, drivers without 3D) |
| `-v`, `--version` | Show the version and exit |
| `-h`, `--help` | Show the help and exit |

### Examples

```bash
gossip -P aws --aws-profile prod --aws-region eu-west-1
gossip -P vault --vault-addr https://bao.example.com:8200 --vault-mount kv
gossip -P k8s --kube-context staging --kube-namespace payments
gossip --read-only --audit-log          # safe browsing with a local audit trail
```
