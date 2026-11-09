# Changelog

Versions follow [SemVer](https://semver.org/). Releases and their checksums are on the
[GitHub releases page](https://github.com/sincorchetes/gossip/releases).

## 0.0.2 — 2026-11-09

### Security
- Updated `pyasn1` to 0.6.5, which fixes four known vulnerabilities.
- Azure Key Vault addresses are now recognised by their parsed host name (it must end in
  `.vault.azure.net`) instead of a substring match, so look-alike URLs are no longer accepted.
- Hash-pinned dependency installs use `--only-binary :all:` wherever a wheel exists. macOS Intel
  builds `cryptography` from source because no wheel is published for it.
- Workflows run with read-only permissions by default, with write access granted per job, and
  CI downloads enforce HTTPS.
- `github/codeql-action` steps are pinned to the same version and updated together.

### Changed
- The *New Version* and *Create secret* dialogs can be resized; the text box grows with the window.
- `gossip -h` / `gossip -v` now show their own help texts in the active language instead of
  argparse's English-only ones.
- The version is now consistent across `src/__init__.py`, `pyproject.toml`, `flake.nix` and the
  AppStream metadata, and a test fails if they drift apart.

### Fixed
- The *Dependency audit* workflow was invalid YAML and did not start.
- The macOS x86_64 release build failed on `cryptography`; the release now includes both macOS
  architectures.

## 0.0.1 — 2026-10-27

Initial release.
