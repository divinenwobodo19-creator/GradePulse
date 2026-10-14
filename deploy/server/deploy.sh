#!/usr/bin/env bash
# Deploy GradePulse from this computer to the server.
#
#   SERVER=ubuntu@1.2.3.4 DOMAIN=gradepulse.duckdns.org ./deploy/server/deploy.sh
#
# Copies the code (from git, so local junk is not sent), writes the server's
# .env from your local .env plus the production settings, then builds and
# starts the stack. Data lives in Docker volumes on the server and survives
# redeploys. SSH key: ~/.ssh/gradepulse_server (override with SSH_KEY).
set -euo pipefail

: "${SERVER:?set SERVER, e.g. ubuntu@1.2.3.4}"
: "${DOMAIN:?set DOMAIN, e.g. gradepulse.duckdns.org}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/gradepulse_server}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH=(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SERVER")
REMOTE_DIR="gradepulse"

[ -f "$ROOT/.env" ] || { echo "No .env in $ROOT"; exit 1; }

echo "→ sending code ($(git -C "$ROOT" rev-parse --short HEAD))"
git -C "$ROOT" archive --format=tar HEAD | "${SSH[@]}" "mkdir -p $REMOTE_DIR && tar -x -C $REMOTE_DIR"

echo "→ writing the server's .env"
{
  # Everything from the local .env except settings the server decides itself.
  grep -vE '^\s*(GRADEPULSE_ENV|GRADEPULPE_ENV|FRONTEND_URL|TRUST_FORWARDED_FOR|DOMAIN|BRAIN_STATE_PATH|CONFIG_PATH|USER_DB_PATH|BACKUP_DIR|SEED_DEMO_DATA|RATE_LIMIT_[A-Z_]+)\s*=' "$ROOT/.env"
  echo "DOMAIN=$DOMAIN"
} | "${SSH[@]}" "umask 077 && cat > $REMOTE_DIR/.env"

echo "→ building and starting (first run takes several minutes)"
"${SSH[@]}" "cd $REMOTE_DIR && docker compose -f deploy/server/docker-compose.server.yml --env-file .env up -d --build --remove-orphans"

echo "→ waiting for https://$DOMAIN"
for i in $(seq 1 60); do
  if curl -fsS -m 10 "https://$DOMAIN/api/health" | grep -q '"engine":"GradePulse"'; then
    echo "✓ GradePulse is live at https://$DOMAIN"; exit 0
  fi
  sleep 10
done
echo "Not answering yet. Check: ${SSH[*]} 'cd $REMOTE_DIR && docker compose -f deploy/server/docker-compose.server.yml logs --tail 50'"
exit 1
