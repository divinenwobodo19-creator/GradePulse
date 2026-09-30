#!/usr/bin/env bash
# GradePulse demo bundle control.
#
#   ./run-demo.sh prepare   # build images (run at home, internet on)
#   ./run-demo.sh start     # boot the stack (venue, internet off is fine)
#   ./run-demo.sh seed      # create the two pilot schools + rosters + history
#   ./run-demo.sh status    # container + health summary
#   ./run-demo.sh stop      # stop containers (data kept)
#   ./run-demo.sh reset     # stop and WIPE all demo data (fresh start)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f $DIR/docker-compose.demo.yml"
API="${DEMO_API:-http://localhost:8000}"

health() {
  curl -sf "$API/health" 2>/dev/null | grep -q '"engine":"GradePulse"' || { echo "engine check failed at $API"; return 1; }
}

wait_health() {
  echo -n "waiting for API health"
  for i in $(seq 1 30); do
    if health; then echo " — OK"; return 0; fi
    echo -n "."
    sleep 2
  done
  echo " — FAILED (check: docker compose logs api)"
  return 1
}

case "${1:-}" in
  prepare)
    $COMPOSE build
    ;;
  start)
    $COMPOSE up -d
    wait_health
    echo "Demo is live — open http://localhost:3000"
    ;;
  seed)
    python3 "$DIR/../pilot_seed.py" --api "$API" --scores
    ;;
  status)
    $COMPOSE ps
    echo "---"
    curl -s "$API/health" || echo "api not responding"
    ;;
  stop)
    $COMPOSE stop
    ;;
  reset)
    $COMPOSE down -v
    echo "Demo data wiped."
    ;;
  *)
    echo "Usage: $0 {prepare|start|seed|status|stop|reset}"
    exit 1
    ;;
esac