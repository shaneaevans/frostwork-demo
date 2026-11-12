#!/usr/bin/env sh
# Default: released wheels. Contributor override: ./setup.sh --local /path/to/frostwork
set -eu
cd "$(dirname "$0")"

if [ "${1:-}" = "--local" ]; then
  checkout="${2:-${FROSTWORK_DIR:-../frostwork}}"
  if [ ! -f "$checkout/Cargo.toml" ] || [ ! -f "$checkout/pyproject.toml" ]; then
    echo "No Frostwork checkout at $checkout" >&2
    exit 1
  fi
  shift
  if [ "$#" -gt 0 ]; then shift; fi
  uv sync --locked "$@"
  uv pip install --python .venv/bin/python --reinstall-package frostwork --editable "$checkout[webpoet]"
  echo "Local Frostwork installed. Use uv run --no-sync to keep the editable override."
else
  exec uv sync --locked "$@"
fi
