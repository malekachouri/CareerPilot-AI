#!/usr/bin/env bash
# Regenerates the typed web API client from the FastAPI OpenAPI schema. CI fails if the result differs
# from what is committed, so the frontend can never drift from the backend contract.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/apps/web/src/lib/api"
(cd "$root/apps/api" && ENV=test uv run --quiet python -c \
  "import json; from careerpilot.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))") \
  > "$out/openapi.json"
(cd "$root/apps/web" && pnpm exec openapi-typescript "$out/openapi.json" -o "$out/schema.d.ts" >/dev/null)
echo "API client regenerated: apps/web/src/lib/api/schema.d.ts"
