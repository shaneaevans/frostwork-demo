#!/usr/bin/env sh
# Link the frostwork library into vendor/ and install everything.
#
# The demo depends on frostwork through an editable local path (see pyproject.toml). uv reads a
# single, fixed path — `vendor/frostwork` — which this script populates as a (gitignored) symlink to
# wherever your frostwork checkout actually lives. Run this instead of a bare `uv sync`.
#
# It looks in, in order:
#   1. $FROSTWORK_DIR   — explicit override, e.g.  FROSTWORK_DIR=/path/to/frostwork ./setup.sh
#   2. ../frostwork     — the documented "clone it as a sibling" layout
#   3. ~/src/frostwork
# Already have a valid vendor/frostwork symlink? It's left as-is.
set -e
cd "$(dirname "$0")"

# frostwork is a maturin project rooted at the repo top (pyproject.toml + Cargo.toml there).
link_target="pyproject.toml"

# Honour an existing, still-valid link (lets you point vendor/ wherever you like by hand).
if [ -f "vendor/frostwork/$link_target" ]; then
  echo "Using existing vendor/frostwork -> $(readlink vendor/frostwork 2>/dev/null || echo vendor/frostwork)"
else
  found=""
  for cand in "$FROSTWORK_DIR" ../frostwork "$HOME/src/frostwork"; do
    if [ -n "$cand" ] && [ -f "$cand/$link_target" ]; then
      found="$(cd "$cand" && pwd)"
      break
    fi
  done

  if [ -z "$found" ]; then
    echo "Could not find a frostwork checkout." >&2
    echo "Clone it next to this repo (../frostwork), or point at it explicitly:" >&2
    echo "  FROSTWORK_DIR=/path/to/frostwork ./setup.sh" >&2
    exit 1
  fi

  mkdir -p vendor
  ln -sfn "$found" vendor/frostwork
  echo "Linked vendor/frostwork -> $found"
fi

exec uv sync "$@"
