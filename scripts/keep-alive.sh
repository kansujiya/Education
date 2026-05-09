#!/usr/bin/env bash
# M-9 keep-alive: prevent Oracle Always-Free reclaim.
# Add to crontab: */5 * * * * /home/ubuntu/education/scripts/keep-alive.sh
set -euo pipefail
curl -fsS http://localhost:8000/healthz >/dev/null
