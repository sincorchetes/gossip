# Graphical User Interface (GUI) Guide

**Gossip** provides a native GNOME design built strictly according to the **GNOME Human Interface Guidelines (HIG)** using modern **Libadwaita** and **GTK4**.

---

## 1. Header Bar Controls

The top header bar provides all global controls, context selectors, and status indicators:

```text
[ Provider Selector ▾ ]  [ Context Switcher ⚙ ]  [ ⟳ Refresh ]  ------ [ Gossip (Subtitle) ] ------  [ ☀/☾ Theme ]  [ ES / EN ]  [ ℹ About ]
```

* **Provider Dropdown Switcher**:
  Allows hot-swapping between **Google Cloud (GCP)**, **Amazon Web Services (AWS)**, **Microsoft Azure (Key Vault)**, and **Ansible Vault**. Changing the provider triggers an immediate, non-blocking strategy replacement.
* **Context Switcher Button**:
  Adapts polymorphically to the active backend:
  * In GCP: Displays the current GCP project ID; clicking opens the project search and switch modal.
  * In AWS: Displays active profile and region (`AWS: default (eu-west-1)`); clicking opens the profile and region modal.
  * In Azure: Displays active Key Vault name; clicking opens the vault name dialog.
  * In Ansible Vault: Displays selected YAML file name; clicking opens the vault file and password selector.
* **Refresh Button (`⟳`)**:
  Re-queries the active provider asynchronously and updates secrets without freezing the interface.
* **Notification Banner**:
  An in-window AdwBanner appears automatically if credentials are missing or connection errors occur, showing detailed instructions to resolve authentication.
* **Theme Toggle (`☀/☾`)**:
  Toggles between light theme and sleek dark mode in real time.
* **Language Switcher (`ES / EN`)**:
  Switches the user interface, labels, tooltips, and dialogs dynamically between English and Spanish.
* **About Button (`ℹ`)**:
  Presents the `Adw.AboutWindow` with version info, authors, links to issue tracker, and website.

---

## 2. Sidebar (Secrets Navigation)

The sidebar provides discovery, live search, and secret selection:

* **Live Search Filter**:
  Instant case-insensitive filtering across secret IDs and labels.
* **Create Secret Button (`+`)**:
  Opens the creation dialog:
  * Secret ID / Name (validates naming rules for each cloud backend).
  * Initial payload (optional; allows creating empty secrets).
  * Replication policy (Automatic or User-Managed multi-region for GCP).
  * Key-value labels / tags.
* **Secret Items List**:
  Each row shows the secret name, creation date, and status badges. Selecting a row loads its metadata, versions, and payload into the main view.

---

## 3. Detail Pane (Secret Inspection & Management)

When a secret is selected, the right-hand panel displays cards organized with Libadwaita preferences groups:

### General Information Card
* **Resource Name**: Full cloud identifier (e.g. `projects/123/secrets/database_password` or ARN). Includes a quick **Copy** button.
* **Creation Date**: Formatted local date and time.
* **Replication**: Configured cloud replication (e.g., Automatic vs specific regions).
* **Labels / Tags**: Key-value labels displayed as distinct pills.

### Secret Value (Payload) Card
* **Shoulder-Surfing Protection**: Secret payload text is masked by default with bullets (`••••••••`).
* **Reveal Button (Eye Icon)**: Toggles visibility between masked and plaintext.
* **Copy Button**: Copies payload directly to system clipboard, displaying an `Adw.Toast` confirmation.
* **Binary Payload Support**: If a payload contains binary data (e.g., certificates or raw bytes), Gossip automatically detects it and renders a clean hex dump alongside total byte count.

### Version History Card
* **Complete Version Timeline**: Lists all versions ordered chronologically (newest first).
* **Status Badges**:
  * `ENABLED` (Active): Fully accessible.
  * `DISABLED`: Suspended version; payload cannot be accessed until re-enabled.
  * `DESTROYED`: Payload has been permanently destroyed.
* **Version Management**:
  * **Enable / Disable Switch**: Toggle versions active or inactive (supported on GCP and Azure).
  * **Destroy Version (Trash Icon)**: Permanently and irreversibly destroys the version's payload (with safety confirmation dialog).
* **New Version Button (`+ New Version`)**:
  Opens a modal to append a new version payload to the secret without altering its name or configuration.

---

## 4. Deleting a Secret

To delete a secret entirely:

1. Click the destructive **Delete Secret** button in the detail view.
2. An `Adw.MessageDialog` will appear asking for confirmation.
3. Confirming permanently deletes the secret and all its associated versions across the cloud provider or local vault file.
