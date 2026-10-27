#!/usr/bin/env bash
# Copy the license files of the MSYS2 packages whose DLLs are bundled in a Windows build.
#
# Usage: collect_msys2_licenses.sh <bundle-dir> <output-dir> [msys2-prefix]   (default prefix: /ucrt64)
set -euo pipefail

BUNDLE="${1:?usage: $0 <bundle-dir> <output-dir> [prefix]}"
OUT="${2:?usage: $0 <bundle-dir> <output-dir> [prefix]}"
PREFIX="${3:-/ucrt64}"

if ! command -v pacman >/dev/null 2>&1; then
  echo "pacman not available: skipping MSYS2 license collection"
  exit 0
fi

mkdir -p "$OUT"
declare -A done_packages=()

while IFS= read -r -d '' dll; do
  source_dll="$PREFIX/bin/$(basename "$dll")"
  [ -e "$source_dll" ] || continue
  package="$(pacman -Qo "$source_dll" 2>/dev/null | sed -n -E 's/.* is owned by ([^ ]+) .*/\1/p' | head -n 1 || true)"
  [ -n "$package" ] || continue
  [ -z "${done_packages[$package]:-}" ] || continue

  # MSYS2 installs license files under <prefix>/share/licenses/<name>, with or without the prefix
  short="${package#mingw-w64-ucrt-x86_64-}"
  for candidate in "$package" "$short"; do
    if [ -d "$PREFIX/share/licenses/$candidate" ]; then
      mkdir -p "$OUT/$short"
      cp -rL "$PREFIX/share/licenses/$candidate/." "$OUT/$short/"
      done_packages[$package]=1
      break
    fi
  done
done < <(find "$BUNDLE" -type f -name '*.dll' -print0)

echo "Collected license files of ${#done_packages[@]} MSYS2 packages"
