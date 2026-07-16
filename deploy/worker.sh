#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.worker.yml"
APP_ENV_FILE="${APP_ENV_FILE:-${REPO_ROOT}/.env.production}"
WORKER_RUNTIME_DIR="${WORKER_RUNTIME_DIR:-${REPO_ROOT}/runtime}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-mamografia-${USER:-worker}}"

export APP_ENV_FILE WORKER_RUNTIME_DIR COMPOSE_PROJECT_NAME
export HOST_UID="${HOST_UID:-$(id -u)}"
export HOST_GID="${HOST_GID:-$(id -g)}"

compose() {
  docker compose \
    --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${APP_ENV_FILE}" \
    --file "${COMPOSE_FILE}" \
    "$@"
}

require_environment() {
  if [[ ! -f "${APP_ENV_FILE}" ]]; then
    echo "No existe el archivo de entorno: ${APP_ENV_FILE}" >&2
    echo "Usa deploy/production.env.example como referencia." >&2
    exit 1
  fi

  python3 "${SCRIPT_DIR}/validate_env.py" "${APP_ENV_FILE}"

  if ! docker info >/dev/null 2>&1; then
    echo "El usuario actual no puede acceder al daemon de Docker." >&2
    exit 1
  fi
}

prepare_runtime() {
  mkdir -p \
    "${WORKER_RUNTIME_DIR}/uploads" \
    "${WORKER_RUNTIME_DIR}/tmp" \
    "${WORKER_RUNTIME_DIR}/cache" \
    "${WORKER_RUNTIME_DIR}/julia-depot"
  chmod -R 700 "${WORKER_RUNTIME_DIR}"
}

command_name="${1:-help}"
shift || true

case "${command_name}" in
  config)
    require_environment
    compose config --quiet
    echo "Configuracion Compose valida."
    ;;
  build)
    require_environment
    prepare_runtime
    compose build --pull worker
    ;;
  start)
    require_environment
    prepare_runtime
    compose up --detach --build --remove-orphans worker
    compose ps
    ;;
  stop)
    require_environment
    compose down
    ;;
  restart)
    require_environment
    compose restart worker
    compose ps
    ;;
  update)
    require_environment
    git -C "${REPO_ROOT}" pull --ff-only origin develop
    prepare_runtime
    compose build --pull worker
    compose up --detach --remove-orphans worker
    compose ps
    ;;
  logs)
    require_environment
    compose logs --follow --tail "${LOG_TAIL:-200}" worker
    ;;
  status)
    require_environment
    compose ps
    ;;
  test)
    require_environment
    prepare_runtime
    compose build worker
    compose run --rm --no-deps worker \
      python3 -m unittest discover -s web/tests -p 'test_*.py'
    compose run --rm --no-deps worker \
      julia --project=/app/simulator -e 'using Pkg; Pkg.test()'
    ;;
  help|*)
    cat <<'EOF'
Uso: ./deploy/worker.sh <comando>

Comandos:
  config   Valida el Compose y las variables requeridas.
  build    Construye la imagen compartida Python/Julia.
  start    Construye e inicia solamente el worker.
  stop     Detiene solamente este proyecto Compose.
  restart  Reinicia el worker sin reconstruir la imagen.
  update   Actualiza develop, reconstruye y levanta el worker.
  logs     Sigue los logs sanitizados del worker.
  status   Muestra el estado y healthcheck del contenedor.
  test     Ejecuta las pruebas Python y Julia dentro de la imagen.
EOF
    ;;
esac
