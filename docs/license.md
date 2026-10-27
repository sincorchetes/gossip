# License and third-party software

## Gossip

Gossip is free software licensed under the **GNU General Public License, version 3 or (at your option) any later version** (SPDX: `GPL-3.0-or-later`). Copyright © 2026 Álvaro Castillo; the AI coding assistant that helped write it is credited as a collaborator in `AUTHORS.md`. The full text is in [`LICENSE`](https://github.com/sincorchetes/gossip/blob/main/LICENSE).

## Third-party software

Gossip is built on open-source software that its packages bundle, each under its own license:

| Group | Examples | Typical licenses |
|---|---|---|
| GNOME platform | GTK 4, libadwaita, GLib, Pango, GdkPixbuf, librsvg, PyGObject | LGPL-2.1-or-later |
| Cloud SDKs | boto3, Google Cloud Secret Manager, gRPC, Azure SDK | Apache-2.0, MIT |
| Ansible | `ansible-core`, `ansible-vault` | GPL-3.0-or-later |
| Cryptography and utilities | cryptography, PyYAML, requests, certifi | Apache-2.0 or BSD, MIT, MPL-2.0 |
| Runtime | Python, OpenSSL, the PyInstaller bootloader | PSF-2.0, Apache-2.0, GPL-2.0-or-later with bootloader exception |

The complete, generated list (names, pinned versions, licenses, project URLs and every license text) is in [`THIRD_PARTY_NOTICES.md`](https://github.com/sincorchetes/gossip/blob/main/THIRD_PARTY_NOTICES.md). It is also shown, summarized, in the application's **About** dialog.

## Where to find the licenses in each package

| Package | Location |
|---|---|
| Linux `.tar.gz` | `gossip/LICENSE`, `gossip/THIRD_PARTY_NOTICES.md`, `gossip/licenses/system/` |
| Linux `.deb` / `.rpm` | `/opt/gossip/` (same layout), `/usr/share/doc/gossip/copyright`, `/usr/share/licenses/gossip/` |
| Windows `.zip` / `.msi` | next to `gossip.exe`: `LICENSE`, `THIRD_PARTY_NOTICES.md`, `licenses\msys2\` |
| macOS `.dmg` / `.tar.gz` | `gossip.app/Contents/Resources/` (`LICENSE`, `THIRD_PARTY_NOTICES.md`, `licenses/`) |

`licenses/` holds the license files of the C libraries that were actually bundled into that package (copied from the Debian, MSYS2 or Homebrew packages they came from).

## Replacing LGPL libraries

Libraries under the LGPL (GTK, GLib, Pango, ...) are shipped as separate shared libraries, not statically linked, so you can replace them with your own build of the same library version. Their source code is available from the project pages listed in the notices.

## Contributing

Contributions are accepted under the same license (GPL-3.0-or-later). Do not add code that is only available under GPL-2.0-only or under a license that cannot be combined with GPL-3.0.

## Regenerating the notices

`THIRD_PARTY_NOTICES.md` is generated from the hashed lock files with `python scripts/generate_third_party_notices.py`; the weekly dependency workflow does it automatically, and a test fails if a locked package is missing from the file.
