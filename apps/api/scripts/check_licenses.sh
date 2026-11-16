#!/usr/bin/env bash
# Fails if a runtime dependency has a licence outside the allow-list in docs/FREE_AND_OPEN_SOURCE_STACK.md §14.
set -euo pipefail
cd "$(dirname "$0")/.."
ALLOW="MIT;BSD;Apache;ISC;MPL;Mozilla Public License;PSF;Python Software Foundation;Unlicense;CC0;PostgreSQL"
packages=$(uv export --no-dev --no-hashes --no-emit-project -q | sed -n 's/^\([A-Za-z0-9_.-]*\)==.*/\1/p')
# shellcheck disable=SC2086
uv run pip-licenses --partial-match --allow-only="$ALLOW" --packages $packages --format=plain
