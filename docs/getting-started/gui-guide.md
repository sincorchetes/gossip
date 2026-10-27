# Graphical User Interface (GUI) Guide

**Gossip** provides a native GNOME design built according to the **GNOME Human Interface Guidelines (HIG)** using **Libadwaita** and **GTK4**.

---

## 1. Header Bar Controls

The top header bar provides the global controls, the context selector and the status indicators:

```text
[ Provider ▾ ] [ Context ] [ ⟳ ] [ Import/Export ] [ 🔒 Read-only ] ---- Gossip (subtitle) ---- [ ☀/☾ ] [ ES / EN ] [ ℹ ]
```

* **Provider dropdown**:
  Hot-swaps between **Google Cloud (GCP)**, **AWS Secrets Manager**, **AWS Parameter Store**, **Azure Key Vault**, **Ansible Vault**, **HashiCorp Vault / OpenBao** and **Kubernetes Secrets**. Gossip remembers the last one you used (see [Security & Privacy](../security.md)).
* **Context button**:
  Adapts to the active backend. The window subtitle always shows what you are looking at.

  | Provider | Context shown | The button opens |
  |---|---|---|
  | GCP | Project ID | Project search and switch dialog |
  | AWS / Parameter Store | `profile (region)` | Profile and region dialog |
  | Azure | Key Vault name | Vault name dialog, with the vaults found by the Azure CLI (or the reason it could not list them) |
  | Ansible Vault | Vault file name | File and password dialog |
  | HashiCorp Vault / OpenBao | `server (mount)` | Server address, KV v2 mount, namespace and token |
  | Kubernetes | `context / namespace` | Kubeconfig context and the namespaces of that cluster |

* **Refresh (`⟳`)**: re-queries the provider in the background without freezing the window.
* **Import / Export menu**: see section 7. In read-only mode only *Export* is offered.
* **Read-only toggle (🔒)**: blocks creating, editing and deleting. See section 8.
* **Notification banner**: appears when credentials are missing or a connection fails, with instructions to fix it. Unreachable servers time out after a few seconds with a clear message instead of spinning forever.
* **Theme toggle (`☀/☾`)**: switches between light and dark mode instantly.
* **Language switcher (`ES / EN`)**: switches every label, tooltip and dialog between English and Spanish.
* **About (`ℹ`)**: version, authors, license, third-party notices and credits.

---

## 2. Sidebar (Secrets Navigation)

* **Live search** (`Ctrl+F` — `Cmd+F` on macOS — to focus, `Esc` to clear): instant, case-insensitive filtering across names, descriptions and labels. Several words must all match, and a message appears when nothing does.

  | Query | Shows |
  |---|---|
  | `db password` | Secrets containing both words |
  | `label:env` | Secrets that have an `env` label |
  | `label:env=prod` | Secrets whose `env` label is exactly `prod` |
  | `db -legacy` | Secrets matching `db` but not `legacy` |

* **Create secret (`+`)**: opens the creation dialog, adapted to the provider (hidden in read-only mode):

  | Provider | What you enter |
  |---|---|
  | GCP | Secret ID, initial payload, labels |
  | AWS Secrets Manager | Name, optional description, payload, tags |
  | AWS Parameter Store | Parameter name (e.g. `/app/prod/db`), optional description, value, tags. Stored as an encrypted `SecureString` |
  | Azure | Name, content type, payload, tags |
  | Ansible Vault | Variable name and value (numbers, booleans, lists and mappings keep their type) |
  | HashiCorp Vault / OpenBao | Secret path and value. A JSON object becomes several keys; any other text is stored under the key `value` |
  | Kubernetes | Secret name and keys. A JSON object of strings becomes several keys; any other text is stored under `value` |

  Creating **never overwrites** an existing secret on any provider: you get "already exists, use New Version" instead.
* **Secret list**: each row shows the name, a short description and the date. Selecting one loads its metadata and versions. The value itself is only fetched when you reveal or copy it.
  * **Tree view**: names with `/` (AWS, Parameter Store, Vault) are grouped in folders that open and close with a click, each showing how many secrets it holds. Small lists start expanded; long ones start collapsed. While you search, the matches are listed flat with their full names.
  * **Large lists**: the list is virtualized, so thousands of secrets stay responsive.
  * **Age flag**: a yellow pill such as `200 d` marks secrets not changed for 90 days or more (`--stale-days DAYS` or `GOSSIP_STALE_DAYS` changes it; `0` turns it off). It uses the last-changed date the provider reports.

---

## 3. Detail Pane (Inspection & Management)

### General information
* **Edit** (pencil, hidden in read-only mode): change the labels / tags (one `key=value` per line) and, where the provider supports it, the description. Supported by GCP, AWS Secrets Manager, Parameter Store (tags), Azure, Vault / OpenBao and Kubernetes. The value is never touched.
* **Resource name** with a quick **Copy** button, **creation date**, **replication** (or *Mount* / *Namespace* for Vault and Kubernetes) and **labels / tags**.

### Secret value
* **Masked by default** with bullets (`••••••••`), so nothing sensitive is visible over your shoulder.
* **Reveal (eye)** shows or hides it. Hiding forgets the value from memory.
* **Copy** puts it on the clipboard, which is wiped automatically after 30 seconds.
* **Multi-key secrets** (Vault, Kubernetes, Parameter Store with JSON) are shown and edited as a JSON object. A single `value` key is shown as plain text.
* **Table view**: when the revealed value is a JSON object, the table button shows one row per key, each with its own copy button, so you can copy just `password` without the rest.
* **Copy** and **Copy key** place the value on the clipboard marked as sensitive, so clipboard managers that honour it (KDE Klipper, KeePassXC, macOS and Windows clipboard history) do not keep it.
* **Binary values**: AWS Secrets Manager binaries and Kubernetes binary keys appear as `base64:<data>` and are written back as the same bytes when you save. GCP shows a hex dump.

### Version history
* **Timeline** with the newest first. Badges: `Enabled`, `Disabled`, `Destroyed`, or the provider's labels (`Current`, `Previous`, Parameter Store labels).
* **Version actions** (hidden in read-only mode):
  * *Disable / Enable*: GCP, Azure and HashiCorp Vault (soft-delete and undelete).
  * *Destroy*: GCP and HashiCorp Vault, permanent and irreversible (with confirmation).
* **Per provider**:
  * Ansible Vault keeps the last five saves as backups and lists the generations in which the variable existed.
  * Kubernetes has no history: each Secret has one version (its `resourceVersion`).
* **New Version** appends a new value without changing the secret's name or configuration. The password-generator button (key icon) generates a random password (length, character kinds, and an option to avoid look-alike characters) and puts it in the text box; it is also available when creating a secret.
* **Restore** (undo icon on an older, readable version): saves that version's value again as a new current version after confirmation. Nothing is lost; the history only grows. Not offered by Kubernetes, which keeps no history.

---

## 4. Deleting a Secret

1. Click the destructive **Delete** button in the detail view.
2. Confirm in the dialog.

What happens depends on the provider:

* **AWS Secrets Manager**: the secret is **scheduled for deletion and can be restored for 7 days**. Tick *Delete immediately, without a recovery window* in the dialog to skip that.
* **Azure Key Vault**: soft-deleted by the service (the name stays reserved while it is recoverable).
* **Others**: the secret and all its versions are removed and this cannot be undone.

---

## 5. Comparing Versions

When a secret has two or more versions, **Compare** opens a diff window:

1. Choose the *From* and *To* versions (by default the previous one and the latest).
2. Click **Compare**. Gossip fetches both values in the background and shows a unified diff: added lines in green, removed lines in red.
3. JSON values are normalized (sorted keys, indentation), so a change in formatting alone is not reported.

> [!WARNING]
> The diff shows values in clear text. They are discarded when the window closes or the inactivity lock fires.

---

## 5b. Comparing with Another Secret

The second compare button (next to the first) opens **Compare with another secret**. Pick a place to compare against: any provider in its current context, or one of the five most recent contexts you used with that provider (for example the *staging* and *prod* projects). The secrets there are listed with a filter; choose one and press **Compare** to see the unified diff against the current secret. Ansible Vault is only offered in its current file, because another vault would need its own password.

---

## 6. Inactivity Lock

After 5 minutes without keyboard, mouse or scroll input, Gossip hides the revealed value, removes it from memory, closes any open diff window, clears the clipboard if it still holds a secret copied from Gossip, drops the HashiCorp Vault token you typed, and **locks the Ansible vault**. When you return, values are fetched again only if you ask, and the Ansible password is requested again (or re-read from your private password file).

The same happens immediately when the **screen locks or the computer suspends** (Linux and BSD, through D-Bus: GNOME, KDE and `logind`). On macOS and Windows only the inactivity timer applies.

Change the delay with `--idle-lock SECONDS` or `GOSSIP_IDLE_LOCK_SECONDS` (`0` disables the timer).

---

## 7. Exporting and Importing Secrets

The **Import / Export** menu moves secrets between environments or keeps a snapshot.

* **Export secrets…** writes a JSON file with every secret listed in the sidebar (name, description and labels). Values are **not included** unless you tick *Include secret values*; then the file holds them in clear text and is created readable only by you (`0600`).
* **Import secrets…** reads a Gossip export, or a plain `{ "name": "value" }` JSON/YAML mapping, and opens a **preview**: how many secrets are new and how many already exist, with a row per entry. Choose what to do with those that exist: **skip** them (keep the current value) or **add the imported value as a new version**. Existing secrets are never overwritten; a summary lists what was created, versioned, skipped and what failed.
* Multi-key secrets (Vault, Kubernetes) travel as JSON text, so you can export from one provider and import into another.

```json
{
  "format": "gossip-export", "version": 1, "provider": "gcp",
  "secrets": [{ "id": "db_password", "labels": {"env": "prod"}, "value": "…" }]
}
```

> [!NOTE]
> Exports contain the latest version of each secret. For Ansible Vault, dictionaries, lists, numbers and booleans are exported as native JSON values and restored with their type.

---

## 8. Read-only Mode

The **lock button** in the header bar turns read-only mode on and off without restarting:

* **On**: the *Create*, *New Version* and *Delete* buttons and the version actions disappear, *Import* is removed from the menu, and the subtitle adds "read-only". Any write action that is still triggered only shows a notice and never reaches the provider.
* **Off**: everything is available again.

Start in this mode with `gossip --read-only` or `GOSSIP_READ_ONLY=1`. With **`--read-only` the mode is locked for the whole session**: the button is disabled and cannot be turned off. With the environment variable alone, the button stays usable.

> [!NOTE]
> Read-only mode guards the interface against mistakes. Your credentials still decide what the provider allows, so use a read-only identity when you need a hard guarantee.

---

## 8b. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New secret |
| `Ctrl+F` | Search (`Cmd` on macOS) |
| `F5` / `Ctrl+R` | Reload |
| `Ctrl+Shift+R` | Show / hide the value |
| `Ctrl+Shift+C` | Copy the value |
| `Ctrl+E` | Edit labels and description |
| `Ctrl+Delete` | Delete the secret (with confirmation) |
| `F1` | List the shortcuts |

Icon-only buttons carry accessible names, so screen readers announce what they do. Theme, language and window size are remembered between sessions.

---

## 9. Audit Trail

Start Gossip with `--audit-log [FILE]` (or `GOSSIP_AUDIT_LOG`) to keep a local record of what happens. Each line is a JSON object with the time, provider, context, action and secret name:

```json
{"time": "2026-10-26T10:15:02+00:00", "provider": "aws", "context": "AWS: prod (eu-west-1)", "action": "reveal", "secret": "prod/db"}
```

Recorded actions: `reveal`, `copy`, `copy_key` (with the key name), `create`, `add_version`, `restore_version`, `edit_metadata`, `enable_version`, `disable_version`, `destroy_version`, `delete`, `import` and `export`. **Values are never written**, and keys that could hold them are dropped. By default the file is `audit.jsonl` next to the saved state, private to you, and rotated at 5 MB.

---

## 10. Diagnostics for Bug Reports

The **About** window has a *Troubleshooting* section with a diagnostics report you can copy or save: Gossip, Python, GTK and library versions, the platform, relevant settings and the last 50 debug lines. Credentials, tokens, URLs with passwords and your home directory are removed from the log, and the report never includes projects, vaults, servers, secret names or values. Attach it to an issue instead of describing your setup by hand.
