#!/usr/bin/env bash
# Production smoke test: signup → profile → cards → attempt → progress.
# Run from your laptop against a deployed BASE_URL. Exits non-zero on
# any failure. Doesn't leave durable state behind beyond one user row.
set -euo pipefail

BASE="${1:-${BASE_URL:-http://localhost:8000}}"
EMAIL="smoke-$(date +%s)@example.com"
PASSWORD="smoke-secret-$(openssl rand -hex 6)"

say() { printf "\033[36m▸ %s\033[0m\n" "$*"; }
fail() { printf "\033[31m✗ %s\033[0m\n" "$*"; exit 1; }
ok()   { printf "\033[32m✓ %s\033[0m\n" "$*"; }

say "Health check  — $BASE/healthz"
curl -fsS "$BASE/healthz" >/dev/null || fail "healthz failed"
ok "healthz"

say "Signup"
TOKEN=$(curl -fsS -X POST "$BASE/v1/auth/signup" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
ok "got token"

AUTH="Authorization: Bearer $TOKEN"
EXAM_DATE="$(date -u -d '+60 days' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v+60d '+%Y-%m-%dT%H:%M:%SZ')"

say "Set profile"
curl -fsS -X POST "$BASE/v1/me/profile" -H "$AUTH" -H 'content-type: application/json' \
  -d "{\"exam_id\":\"aws-ccp\",\"exam_date\":\"$EXAM_DATE\",\"daily_minutes\":60}" \
  >/dev/null
ok "profile saved"

say "Fetch plan"
curl -fsS "$BASE/v1/me/plan" -H "$AUTH" >/dev/null
ok "plan fetched"

say "Issue cards"
CARD_ID=$(curl -fsS -X POST "$BASE/v1/me/topics/cloud-concepts.benefits/cards" -H "$AUTH" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["cards"][0]["id"])')
ok "got card $CARD_ID"

say "Attempt card"
curl -fsS -X POST "$BASE/v1/me/cards/$CARD_ID/attempt" -H "$AUTH" -H 'content-type: application/json' \
  -d '{"answer":"I clearly mention pay-as-you-go in my answer."}' >/dev/null
ok "attempt graded"

say "Read progress"
curl -fsS "$BASE/v1/me/progress" -H "$AUTH" >/dev/null
ok "progress fetched"

printf "\n\033[32mAll checks passed for %s as %s.\033[0m\n" "$BASE" "$EMAIL"
