#!/usr/bin/env bash
# Stamp the release version (from a git tag such as v1.2.3) into the sources before building,
# so `gossip --version` and the package metadata match the published release.
#
# Usage: scripts/set_version.sh <tag-or-version> [repo-root]
set -euo pipefail

VERSION="${1:?usage: $0 <tag-or-version> [repo-root]}"
VERSION="${VERSION#v}"
ROOT="${2:-$(dirname "$0")/..}"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
  echo "Refusing to stamp invalid version: $VERSION" >&2
  exit 2
fi

export V="$VERSION"
perl -pi -e 's/^__version__ = ".*"/__version__ = "$ENV{V}"/' "$ROOT/src/__init__.py"
perl -pi -e 'if (!$done && s/^version = ".*"/version = "$ENV{V}"/) { $done = 1 }' "$ROOT/pyproject.toml"
echo "Stamped version $VERSION"
