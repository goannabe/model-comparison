#!/usr/bin/env bash
# Reset the demo's credit counters before the hour is up.
#
# Usage:
#   scripts/reset-quota.sh                                  # local backend, everyone
#   scripts/reset-quota.sh https://<backend-url>            # deployed backend, everyone
#   scripts/reset-quota.sh <url> global                     # only the shared app-wide budget
#   scripts/reset-quota.sh <url> client 203.0.113.9         # one visitor's budget
#
# Reads QUOTA_ADMIN_KEY from webapp/backend/.env (git-ignored). The deployed
# backend must have the same value in its QUOTA_ADMIN_KEY env var.
set -euo pipefail
cd "$(dirname "$0")/.."

URL="${1:-http://localhost:8000}"
SCOPE="${2:-all}"
CLIENT="${3:-}"

KEY="$(grep -E '^QUOTA_ADMIN_KEY=' webapp/backend/.env 2>/dev/null | head -1 | cut -d= -f2-)"
if [ -z "$KEY" ]; then
  echo "QUOTA_ADMIN_KEY not found in webapp/backend/.env" >&2
  exit 1
fi

BODY="{\"scope\": \"$SCOPE\"${CLIENT:+, \"client\": \"$CLIENT\"}}"
curl -sS -X POST "${URL%/}/api/quota/reset/" \
  -H "X-Admin-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
