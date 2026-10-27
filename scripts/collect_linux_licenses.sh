#!/usr/bin/env bash
# Copy the Debian copyright file of every system library bundled in a PyInstaller build, so the
# package ships the real licenses of the C libraries it contains.
#
# Usage: collect_linux_licenses.sh <bundle-dir> <output-dir>
set -euo pipefail

BUNDLE="${1:?usage: $0 <bundle-dir> <output-dir>}"
OUT="${2:?usage: $0 <bundle-dir> <output-dir>}"

if ! command -v dpkg >/dev/null 2>&1 || ! command -v ldconfig >/dev/null 2>&1; then
  echo "dpkg/ldconfig not available: skipping system license collection"
  exit 0
fi

mkdir -p "$OUT"
declare -A done_packages=()
libraries=0

while IFS= read -r -d '' lib; do
  name="$(basename "$lib")"
  host_path="$(ldconfig -p | awk -v n="$name" '$1 == n { print $NF; exit }')"
  [ -n "$host_path" ] || continue
  libraries=$((libraries + 1))

  package="$(dpkg -S "$host_path" 2>/dev/null | head -n 1 | cut -d: -f1 || true)"
  if [ -z "$package" ]; then
    package="$(dpkg -S "$(readlink -f "$host_path")" 2>/dev/null | head -n 1 | cut -d: -f1 || true)"
  fi
  package="${package%%,*}"
  [ -n "$package" ] || continue
  [ -z "${done_packages[$package]:-}" ] || continue

  copyright="/usr/share/doc/$package/copyright"
  if [ -e "$copyright" ]; then
    cp -L "$copyright" "$OUT/$package.copyright"
    done_packages[$package]=1
  fi
done < <(find "$BUNDLE" -type f \( -name '*.so' -o -name '*.so.*' \) -print0)

echo "Collected ${#done_packages[@]} copyright files for $libraries bundled system libraries"
