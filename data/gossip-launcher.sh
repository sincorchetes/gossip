#!/bin/sh
set -e

# Bundle directories
BUNDLE_DIR="/opt/gossip"
INTERNAL_DIR="/opt/gossip/_internal"

# Locate and export Typelib search paths for GObject Introspection
TYPELIB_DIRS=""
for d in \
  "${INTERNAL_DIR}/gi_typelibs" \
  "${INTERNAL_DIR}/girepository-1.0" \
  "${BUNDLE_DIR}/gi_typelibs" \
  "${BUNDLE_DIR}/girepository-1.0" \
  /usr/lib64/girepository-1.0 \
  /usr/lib/x86_64-linux-gnu/girepository-1.0 \
  /usr/lib/aarch64-linux-gnu/girepository-1.0 \
  /usr/lib/girepository-1.0 \
  /usr/local/lib64/girepository-1.0 \
  /usr/local/lib/girepository-1.0
do
  if [ -d "$d" ]; then
    TYPELIB_DIRS="${TYPELIB_DIRS}${TYPELIB_DIRS:+:}$d"
  fi
done

if [ -n "$TYPELIB_DIRS" ]; then
  export GI_TYPELIB_PATH="${TYPELIB_DIRS}${GI_TYPELIB_PATH:+:${GI_TYPELIB_PATH}}"
fi

# Locate and export GSettings Schemas directory
SCHEMA_DIRS=""
for d in \
  "${INTERNAL_DIR}/glib-2.0/schemas" \
  "${BUNDLE_DIR}/glib-2.0/schemas" \
  "${BUNDLE_DIR}/share/glib-2.0/schemas" \
  /usr/share/glib-2.0/schemas \
  /usr/local/share/glib-2.0/schemas
do
  if [ -d "$d" ]; then
    SCHEMA_DIRS="${SCHEMA_DIRS}${SCHEMA_DIRS:+:}$d"
  fi
done

if [ -n "$SCHEMA_DIRS" ]; then
  export GSETTINGS_SCHEMA_DIR="${SCHEMA_DIRS}${GSETTINGS_SCHEMA_DIR:+:${GSETTINGS_SCHEMA_DIR}}"
fi

# Locate and export XDG Data Dirs
XDG_DIRS=""
for d in \
  "${INTERNAL_DIR}/share" \
  "${BUNDLE_DIR}/share" \
  /usr/share \
  /usr/local/share
do
  if [ -d "$d" ]; then
    XDG_DIRS="${XDG_DIRS}${XDG_DIRS:+:}$d"
  fi
done

if [ -n "$XDG_DIRS" ]; then
  export XDG_DATA_DIRS="${XDG_DIRS}${XDG_DATA_DIRS:+:${XDG_DATA_DIRS}}"
fi

exec /opt/gossip/gossip "$@"
