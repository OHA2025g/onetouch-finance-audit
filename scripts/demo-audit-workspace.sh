#!/usr/bin/env bash
# Demo: Finance Audit workspace — entity scope → fail filter → run control → evidence link.
# Requires API on REACT_APP_BACKEND_URL (default http://localhost:8000) and seeded demo data.
set -euo pipefail

API="${REACT_APP_BACKEND_URL:-http://localhost:8000}"
API="${API%/}/api"
EMAIL="${DEMO_EMAIL:-cfo@onetouch.ai}"
PASS="${DEMO_PASSWORD:-demo1234}"
ENTITY="${DEMO_ENTITY:-US-HQ}"

echo "==> Login as ${EMAIL}"
TOKEN=$(curl -sf -X POST "${API}/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASS}\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

auth=(-H "Authorization: Bearer ${TOKEN}")

echo "==> Load audit workspace (entity=${ENTITY})"
AUDIT=$(curl -sf "${API}/dashboard/audit?entity_code=${ENTITY}" "${auth[@]}")
read -r CONTROL_ID CODE <<<"$(echo "$AUDIT" | python3 -c '
import sys, json
d = json.load(sys.stdin)
controls = d.get("controls") or []
failing = [c for c in controls if c.get("last_run_pass") is False]
pick = (failing or controls)[0]
print(pick["id"], pick.get("code", ""))
')"

echo "==> Summary readiness: $(echo "$AUDIT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["summary"].get("audit_readiness_pct"))')%"
echo "==> Selected control ${CODE} (${CONTROL_ID})"

echo "==> Run control test pack"
RUN=$(curl -sf -X POST "${API}/controls/${CONTROL_ID}/run" "${auth[@]}")
echo "$RUN" | python3 -m json.tool

echo "==> Open UI: http://localhost:5175/app/audit?control=${CONTROL_ID}"
echo "    Filter Fail chip, attach evidence in control detail, refresh with no_cache."
