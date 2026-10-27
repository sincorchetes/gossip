# Environment Variables

Gossip reads a few variables of its own and, for each provider, the variables that provider's tooling already uses. Anything you also pass on the command line wins over the environment, and the environment wins over what Gossip remembered from the last run.

!!! note "What is never read from the environment"
    The Ansible Vault **password** is always typed in the dialog. Gossip does not read it from a variable, and `ANSIBLE_VAULT_PASSWORD_FILE` only names a file (see below). Credentials are never written to the state file.

## Gossip

| Variable | Equivalent option | Effect |
|---|---|---|
| `GOSSIP_DEBUG` | `--debug` | Any non-empty value writes redacted diagnostics to stderr. |
| `GOSSIP_READ_ONLY` | `--read-only` | `1` hides and blocks create, edit and delete. The window offers a toggle for it. |
| `GOSSIP_READ_ONLY_LOCKED` | set by `--read-only` | `1` removes the toggle, so read-only mode cannot be switched off from the window. |
| `GOSSIP_AUDIT_LOG` | `--audit-log FILE` | Appends one JSON line per reveal, copy, create, change and delete. Values are never logged. |
| `GOSSIP_STALE_DAYS` | `--stale-days N` | Age in days after which a secret is flagged as stale. Default `90`; `0` turns the flag off. |
| `GOSSIP_IDLE_LOCK_SECONDS` | `--idle-lock N` | Seconds of inactivity before the window locks. Default `300`; `0` disables it. |
| `GOSSIP_REVEAL_SECONDS` | `--reveal-timeout N` | Seconds a revealed value stays visible before it is hidden and dropped from memory. Default `120`; `0` keeps it until you hide it. |
| `GOSSIP_HIDE_ON_BLUR` | `--hide-on-blur` | `1` hides a revealed value as soon as the window loses focus. Off by default. |
| `GOSSIP_STATE_FILE` | — | Full path of `state.json`, replacing the platform default. |
| `GOSSIP_SELFTEST_HEADLESS` | — | `1` lets `--self-test` run without a display (used by CI). |

## Google Cloud (GCP)

| Variable | Used for |
|---|---|
| `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT` | Project preselected at startup, checked in this order. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service-account or external-account key file for Application Default Credentials. |
| `CLOUDSDK_CONFIG` | Alternative gcloud configuration folder (where `gcloud auth application-default login` stores its credentials). |

Credentials come from `google.auth.default()`, so `gcloud auth application-default login`, a service account or Workload Identity all work.

## AWS (Secrets Manager and Parameter Store)

| Variable | Used for |
|---|---|
| `AWS_PROFILE`, `AWS_DEFAULT_PROFILE` | Profile preselected at startup. |
| `AWS_REGION`, `AWS_DEFAULT_REGION` | Region preselected at startup. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Static or temporary credentials, read by boto3. |
| `AWS_SHARED_CREDENTIALS_FILE`, `AWS_CONFIG_FILE` | Alternative locations of `~/.aws/credentials` and `~/.aws/config` (SSO profiles included). |
| `AWS_CA_BUNDLE` | Custom CA bundle for the AWS endpoints (corporate proxies). |
| `AWS_ENDPOINT_URL` | Custom endpoint, for example a VPC endpoint. |

Both AWS providers share the profile and region. Connection and read timeouts are fixed in the client, so a stalled network surfaces as an error instead of freezing the window.

## Azure Key Vault

| Variable | Used for |
|---|---|
| `AZURE_KEYVAULT_NAME`, `AZURE_VAULT_NAME`, `AZURE_VAULT_URL`, `KEYVAULT_NAME` | Vault preselected at startup, checked in this order. |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Service-principal sign-in, read by `DefaultAzureCredential`. |
| `AZURE_CLIENT_CERTIFICATE_PATH` | Certificate-based service principal. |
| `AZURE_USERNAME`, `AZURE_PASSWORD` | Username and password sign-in (not recommended; prefer `az login`). |
| `AZURE_CONFIG_DIR` | Alternative Azure CLI configuration folder. |

`DefaultAzureCredential` tries the environment, managed identity and the Azure CLI session in that order.

## Ansible Vault

| Variable | Used for |
|---|---|
| `ANSIBLE_VAULT_FILE` | Vault file opened at startup. |
| `ANSIBLE_VAULT_PASSWORD_FILE` | Password file offered in the dialog. It is the only source Gossip honours; it never guesses `.vault_pass`-style files. |

## HashiCorp Vault / OpenBao

Both prefixes are accepted; `VAULT_*` is checked before `BAO_*`.

| Variable | Used for |
|---|---|
| `VAULT_ADDR`, `BAO_ADDR` | Server address. Must be `https://`; plain `http://` is accepted only for localhost. |
| `VAULT_TOKEN`, `BAO_TOKEN` | Token offered in the dialog. Without one, the token saved by `vault login` (`~/.vault-token`) is used. |
| `VAULT_NAMESPACE`, `BAO_NAMESPACE` | Namespace (Vault Enterprise and OpenBao). |
| `VAULT_CACERT`, `BAO_CACERT` | CA bundle for a server with a private certificate. Certificates are always verified. |

## Kubernetes

| Variable | Used for |
|---|---|
| `KUBECONFIG` | Colon-separated (`;` on Windows) list of kubeconfig files. Defaults to `~/.kube/config`. |

Clusters that authenticate through an `exec` plugin (`aws eks get-token`, `gke-gcloud-auth-plugin`, `kubelogin`) run that command with your environment, so the variables of the tool in question apply.

## Proxies and certificates

The HTTP clients honour the usual `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`, `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` variables. Gossip has no option to skip certificate verification.

## Display and platform

| Variable | Used for |
|---|---|
| `GSK_RENDERER` | GTK renderer (`ngl`, `gl`, `vulkan`, `cairo`). `--renderer` sets it; `--software-rendering` forces `cairo` and `LIBGL_ALWAYS_SOFTWARE=1`. |
| `LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG` | Interface language when none was chosen (checked in this order); the choice made in the menu is remembered afterwards. |
| `XDG_CONFIG_HOME` | Linux base of the state folder (`~/.config` by default). |
| `APPDATA` | Windows base of the state folder. |

The packaged builds also set `GI_TYPELIB_PATH`, `GSETTINGS_SCHEMA_DIR`, `GDK_PIXBUF_MODULE_FILE`, `XDG_DATA_DIRS` and, on macOS, `DYLD_FALLBACK_LIBRARY_PATH` themselves. You should not need to touch them.

## Flatpak

The sandbox exposes your credential folders read-only (`~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.vault-token`) but **not** your shell environment. Pass variables with `--env`, or persistently with an override:

```bash
flatpak run --env=AWS_PROFILE=prod --env=VAULT_ADDR=https://vault.example.com \
    com.github.sincorchetes.gossip_gcp
flatpak override --user --env=AWS_PROFILE=prod com.github.sincorchetes.gossip_gcp
```

Inside the sandbox the state file lives in `~/.var/app/com.github.sincorchetes.gossip_gcp/config/gossip/state.json`. Files outside the folders above (an Ansible vault, a private CA bundle) need `flatpak override --user --filesystem=<path>:ro`.
