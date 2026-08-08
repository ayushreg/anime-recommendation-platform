#!/usr/bin/env bash
# Kura, one command. macOS and Linux.
#   ./start.sh
#
# Does nothing clever: checks Docker is actually running, then hands over to
# compose. The point is that a first run fails with a sentence you can act on
# instead of a wall of Go stack trace.
set -euo pipefail

printf '\n  \033[35mKura\033[0m  local anime vault\n\n'

if ! command -v docker >/dev/null 2>&1; then
  printf '  \033[31mDocker is not installed.\033[0m\n'
  printf '  Get Docker Desktop: https://www.docker.com/products/docker-desktop/\n\n'
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  printf '  \033[31mDocker is installed but not running.\033[0m\n'
  printf '  Start Docker Desktop, wait for it to settle, then run this again.\n\n'
  exit 1
fi

WEB_PORT="${KURA_WEB_PORT:-3000}"

printf '  \033[2mBuilding and starting. First run downloads a 12k title catalog,\033[0m\n'
printf '  \033[2mso it takes a few minutes. Later runs are seconds.\033[0m\n\n'

if ! docker compose up --build -d; then
  printf '\n  \033[31mCompose failed.\033[0m The usual cause is a port already in use:\n'
  printf '  copy .env.example to .env and change KURA_WEB_PORT or KURA_API_PORT.\n\n'
  exit 1
fi

printf '\n  \033[2mSeeding the catalog. Watch progress with:\033[0m\n'
printf '    docker compose logs -f api\n\n'
printf '  Open      \033[36mhttp://localhost:%s\033[0m\n' "$WEB_PORT"
printf '  Sign in   demo@anime.app  /  demo1234\n\n'
printf '  Stop with:  docker compose down\n\n'
