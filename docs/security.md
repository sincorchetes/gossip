# Security & Privacy

What Gossip keeps, where it keeps it, and what it refuses to do.

---

## Secret values

* Values are **fetched only when you reveal or copy them**, never when you select a secret.
* A revealed value lives in memory only while it is shown. Hiding it, switching secret or the inactivity lock discards it, and so does a timer: a revealed value is hidden automatically after 120 seconds (`--reveal-timeout`), and optionally as soon as the window loses focus (`--hide-on-blur`).
* **Copy** places the value on the clipboard and wipes it after **30 seconds** (only if the clipboard still holds what Gossip put there). The inactivity lock wipes it too.
* The copied value is also **marked as sensitive** (`x-kde-passwordManagerHint`, `org.nspasteboard.ConcealedType` and the Windows clipboard-history exclusions), so clipboard managers and cloud clipboard sync that honour those hints do not store it. These are best-effort conventions: a tool that ignores them still receives the text, which is why the wipe exists.
* The version diff shows clear text and is discarded when its window closes.
* Exports contain values only if you tick *Include secret values*; the file is created readable only by you (`0600`).

## Inactivity and session lock

On Linux and BSD Gossip also locks **as soon as the screen locks or the machine suspends** (it listens to `logind` and the GNOME / freedesktop screensaver on D-Bus). macOS and Windows only use the timer.

After 5 minutes without input (`--idle-lock SECONDS`, `GOSSIP_IDLE_LOCK_SECONDS`, `0` disables) Gossip hides and forgets the value, closes the diff, clears the clipboard, drops the HashiCorp Vault token you typed and locks the Ansible vault.

## Credentials

| Provider | How credentials are obtained | What Gossip stores |
|---|---|---|
| GCP | Application Default Credentials | Nothing |
| AWS / Parameter Store | Standard AWS credential chain and profiles | Nothing |
| Azure | `DefaultAzureCredential` | Nothing |
| Ansible Vault | Password typed each time, or a private password file | Nothing. The password is never read from the environment and password files are never guessed; a file readable by other users is ignored |
| HashiCorp Vault / OpenBao | Token typed in the dialog (memory only), `VAULT_TOKEN` / `BAO_TOKEN`, or `~/.vault-token` | Nothing |
| Kubernetes | Your kubeconfig (token, certificate or `exec` plugin) | Nothing |

## Network rules

* Certificates are **always verified**. There is no option to disable verification: Kubernetes contexts with `insecure-skip-tls-verify` are refused, and Vault has no equivalent switch. Use a custom CA instead (`VAULT_CACERT`, or the cluster's `certificate-authority`).
* The Vault token travels in a header, so `http://` addresses are refused except for `localhost`.
* Connections time out after a few seconds (AWS and Azure retry twice) and report a clear message instead of waiting indefinitely.

## What is remembered between runs

Gossip stores your last provider and context so you do not have to pick them again. The file is `state.json` in the configuration folder, readable only by you:

| Platform | Location |
|---|---|
| Linux | `$XDG_CONFIG_HOME/gossip/` or `~/.config/gossip/` |
| macOS | `~/Library/Application Support/gossip/` |
| Windows | `%APPDATA%\gossip\` |

It holds names such as the GCP project, AWS profile and region, Azure vault, Ansible file **path**, Vault address / mount / namespace and Kubernetes context / namespace. **Passwords, tokens and keys are never saved**: anything whose name looks like a credential is dropped before writing. The file also holds the five most recent contexts of each provider (used by *Compare with another secret*) and your interface preferences (theme, language, window size). Delete the file to forget everything. Inside the Flatpak sandbox the folder is `~/.var/app/com.github.sincorchetes.gossip_gcp/config/gossip/`. The precedence at startup is: command-line option, then the saved choice, then autodetection (environment, CLI tools, kubeconfig).

## Read-only mode

The header lock (or `--read-only`, `GOSSIP_READ_ONLY=1`) hides every control that changes data and blocks the underlying actions. `--read-only` locks the mode for the session. It protects against mistakes in the interface; your credentials still define what the provider allows.

## Audit trail

`--audit-log [FILE]` (or `GOSSIP_AUDIT_LOG`) records reveal, copy, create, change, delete, import and export events as JSON lines in a private file. It stores names, counts and versions, **never values**. Use it together with a read-only identity when you must demonstrate what was accessed.

## Deletion safety

* AWS Secrets Manager deletions are **recoverable for 7 days** unless you tick *Delete immediately*.
* Creating never overwrites an existing secret, on any provider.
* Importing never overwrites existing secrets.
* Ansible Vault keeps the last five saves as backups next to the file.

## Diagnostics report

The *Troubleshooting* section of the About window offers a report for bug reports. It lists versions and settings and the last debug lines with credentials, URLs with passwords and your home directory removed. It never contains projects, vaults, servers, secret names or values.

---

## Releases and supply chain

* Every dependency is pinned with hashes (`--require-hashes`) and GitHub Actions are pinned by commit.
* A weekly **dependency audit** (`pip-audit`, also on every change to the lock files) scans the pinned versions for known vulnerabilities, and each release ships a **CycloneDX SBOM** of the Python dependencies (`gossip-python-sbom-*.cdx.json`).
* Each release ships a `SHA256SUMS.txt` and a signed build-provenance attestation. Verify a download with `sha256sum -c SHA256SUMS.txt` or `gh attestation verify <file> -R sincorchetes/gossip`.
* Third-party licenses are listed in `THIRD_PARTY_NOTICES.md` and in the About dialog. Gossip is licensed under GPL-3.0-or-later.
* `gossip --self-test` verifies that every bundled dependency loads and that encryption works.
