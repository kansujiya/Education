#!/usr/bin/env bash
# M-9: cost-dashboard verification.
#
# This script doesn't fetch live cost data (each provider has its own
# auth and CLI). It prints a checklist of links the operator should
# review immediately after deploy and asks for explicit confirmation
# that they're at $0.
set -euo pipefail

cat <<'EOF'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M-9 cost verification  (free-tier path, see tech-plan.md §18)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open each dashboard and confirm the figure on screen:

  1. Oracle Cloud (or Hetzner CX22)
       Compute → cost: should be $0 (Always-Free) or your fixed €4.5/mo.
       Reachable at:
         • https://cloud.oracle.com/billing/usage
         • or https://console.hetzner.cloud/

  2. Neon — Postgres + pgvector
       Storage usage well under 500 MB.
         • https://console.neon.tech/

  3. Cloudflare R2
       Storage well under 10 GB; egress free anyway.
         • https://dash.cloudflare.com/?to=/:account/r2

  4. Cloudflare Pages
       Build minutes used; should be unlimited free.
         • https://dash.cloudflare.com/?to=/:account/pages

  5. GitHub Actions
       Settings → Billing → Usage. Free for public repos.
         • https://github.com/settings/billing/summary

  6. Anthropic Console — the only line item that actually charges
       Confirm spend alert is set at $5 (for v0.1) or your cap.
         • https://console.anthropic.com/settings/billing

EOF

read -r -p "Are all of the above showing the expected (free) figures? [y/N] " ans
case "$ans" in
  y|Y|yes|YES) printf "\n\033[32m✓ Day-1 cost guard passed.\033[0m\n" ;;
  *) printf "\n\033[31m✗ Investigate the unexpected dashboard before going further.\033[0m\n"; exit 1 ;;
esac
