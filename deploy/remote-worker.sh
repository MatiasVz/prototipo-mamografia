#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

ACTION="${1:-}"
IMAGE_REFERENCE="${2:-}"
VERSION="${3:-}"
DEPLOY_ROOT="${4:-${HOME}/apps/prototipo-mamografia}"
DEPLOY_ROOT="$(realpath -m "${DEPLOY_ROOT}")"
SHARED_DIR="${DEPLOY_ROOT}/shared"
ENV_FILE="${SHARED_DIR}/.env.production"
RUNTIME_DIR="${SHARED_DIR}/runtime"
CURRENT_LINK="${DEPLOY_ROOT}/current"
PREVIOUS_LINK="${DEPLOY_ROOT}/previous"
COMPOSE_PROJECT_NAME="mamografia-${USER}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-360}"

export COMPOSE_PROJECT_NAME
export APP_ENV_FILE="${ENV_FILE}"
export WORKER_RUNTIME_DIR="${RUNTIME_DIR}"
export HOST_UID="${HOST_UID:-$(id -u)}"
export HOST_GID="${HOST_GID:-$(id -g)}"

usage() {
  cat <<'EOF'
Uso:
  remote-worker.sh deploy <imagen> <version> [directorio]
  remote-worker.sh status _ _ [directorio]
  remote-worker.sh rollback _ _ [directorio]

El script administra exclusivamente el proyecto Compose del usuario actual.
EOF
}

require_safe_root() {
  case "${DEPLOY_ROOT}" in
    "${HOME}"/*)
      ;;
    *)
      echo "El directorio de despliegue debe estar dentro de ${HOME}." >&2
      exit 1
      ;;
  esac
}

require_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "El usuario actual no puede acceder al daemon de Docker." >&2
    exit 1
  fi
}

require_environment() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "No existe el archivo privado ${ENV_FILE}." >&2
    echo "Debe crearse manualmente con permisos 600 antes del primer despliegue." >&2
    exit 1
  fi
}

prepare_directories() {
  mkdir -p "${DEPLOY_ROOT}/releases" "${SHARED_DIR}" "${RUNTIME_DIR}"
  chmod 700 "${DEPLOY_ROOT}" "${SHARED_DIR}" "${RUNTIME_DIR}"
}

compose() {
  local compose_file="$1"
  local image_reference="$2"
  shift 2

  APP_IMAGE_REFERENCE="${image_reference}" docker compose \
    --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    --file "${compose_file}" \
    "$@"
}

wait_for_worker() {
  local compose_file="$1"
  local image_reference="$2"
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  local container_id state health

  container_id="$(compose "${compose_file}" "${image_reference}" ps -q worker)"
  if [[ -z "${container_id}" ]]; then
    echo "No se encontro el contenedor del worker." >&2
    return 1
  fi

  while (( SECONDS < deadline )); do
    state="$(docker inspect --format '{{.State.Status}}' "${container_id}" 2>/dev/null || true)"
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container_id}" 2>/dev/null || true)"

    if [[ "${state}" == "running" && "${health}" == "healthy" ]]; then
      return 0
    fi
    if [[ "${state}" == "exited" || "${state}" == "dead" || "${health}" == "unhealthy" ]]; then
      echo "Worker no saludable: state=${state:-unknown} health=${health:-unknown}" >&2
      return 1
    fi
    sleep 5
  done

  echo "El worker no alcanzo estado saludable dentro del tiempo esperado." >&2
  return 1
}

release_compose_file() {
  printf '%s/docker-compose.worker.yml' "$1"
}

release_image() {
  local release_dir="$1"
  [[ -f "${release_dir}/.image" ]] && cat "${release_dir}/.image"
}

activate_release_links() {
  local release_dir="$1"
  local old_current="${2:-}"

  if [[ -n "${old_current}" && "${old_current}" != "${release_dir}" ]]; then
    ln -sfn "${old_current}" "${DEPLOY_ROOT}/previous.new"
    mv -Tf "${DEPLOY_ROOT}/previous.new" "${PREVIOUS_LINK}"
  fi
  ln -sfn "${release_dir}" "${DEPLOY_ROOT}/current.new"
  mv -Tf "${DEPLOY_ROOT}/current.new" "${CURRENT_LINK}"
}

deploy_release() {
  local release_dir="${DEPLOY_ROOT}/releases/${VERSION}"
  local compose_file="$(release_compose_file "${release_dir}")"
  local validator="${release_dir}/deploy/validate_env.py"
  local old_current old_image old_compose

  if [[ -z "${IMAGE_REFERENCE}" || -z "${VERSION}" ]]; then
    usage
    exit 2
  fi
  if [[ ! "${VERSION}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "La version debe ser un hash Git completo de 40 caracteres." >&2
    exit 1
  fi
  if [[ ! "${IMAGE_REFERENCE}" =~ ^ghcr\.io/.+@sha256:[0-9a-f]{64}$ ]]; then
    echo "La imagen debe proceder de GHCR y estar fijada por digest sha256." >&2
    exit 1
  fi
  if [[ ! -f "${compose_file}" || ! -f "${validator}" ]]; then
    echo "La entrega ${VERSION} no contiene los archivos de despliegue esperados." >&2
    exit 1
  fi

  python3 "${validator}" "${ENV_FILE}"
  old_current="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
  old_image="$(release_image "${old_current}" 2>/dev/null || true)"
  old_compose="$(release_compose_file "${old_current}")"

  echo "Descargando imagen inmutable ${IMAGE_REFERENCE}."
  docker pull "${IMAGE_REFERENCE}"
  compose "${compose_file}" "${IMAGE_REFERENCE}" config --quiet
  compose "${compose_file}" "${IMAGE_REFERENCE}" up --detach --no-build --remove-orphans worker

  if wait_for_worker "${compose_file}" "${IMAGE_REFERENCE}"; then
    printf '%s\n' "${IMAGE_REFERENCE}" > "${release_dir}/.image"
    printf '%s\n' "${VERSION}" > "${release_dir}/.version"
    activate_release_links "${release_dir}" "${old_current}"
    {
      printf 'VERSION=%s\n' "${VERSION}"
      printf 'IMAGE=%s\n' "${IMAGE_REFERENCE}"
      printf 'DEPLOYED_AT=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${SHARED_DIR}/deployment.env"
    compose "${compose_file}" "${IMAGE_REFERENCE}" ps
    echo "Despliegue del worker completado y saludable."
    return 0
  fi

  echo "La nueva version fallo. Iniciando reversion controlada." >&2
  compose "${compose_file}" "${IMAGE_REFERENCE}" logs --tail 100 worker >&2 || true

  if [[ -n "${old_current}" && -n "${old_image}" && -f "${old_compose}" ]]; then
    compose "${old_compose}" "${old_image}" up --detach --no-build --remove-orphans worker
    if wait_for_worker "${old_compose}" "${old_image}"; then
      echo "Se restauro correctamente la version anterior." >&2
    else
      echo "ATENCION: la version anterior tampoco recupero un estado saludable." >&2
    fi
  else
    compose "${compose_file}" "${IMAGE_REFERENCE}" stop worker || true
    echo "No existia una version anterior para restaurar." >&2
  fi
  return 1
}

show_status() {
  local current_release current_image current_compose
  current_release="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
  if [[ -z "${current_release}" ]]; then
    echo "No existe un despliegue activo registrado."
    return 1
  fi
  current_image="$(release_image "${current_release}")"
  current_compose="$(release_compose_file "${current_release}")"
  echo "Version activa: $(basename "${current_release}")"
  echo "Imagen activa: ${current_image}"
  compose "${current_compose}" "${current_image}" ps
}

rollback_release() {
  local current_release previous_release previous_image previous_compose
  current_release="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
  previous_release="$(readlink -f "${PREVIOUS_LINK}" 2>/dev/null || true)"
  if [[ -z "${previous_release}" ]]; then
    echo "No existe una version anterior registrada para revertir." >&2
    exit 1
  fi

  previous_image="$(release_image "${previous_release}")"
  previous_compose="$(release_compose_file "${previous_release}")"
  docker pull "${previous_image}"
  compose "${previous_compose}" "${previous_image}" up --detach --no-build --remove-orphans worker
  wait_for_worker "${previous_compose}" "${previous_image}"
  activate_release_links "${previous_release}" "${current_release}"
  echo "Reversion completada a $(basename "${previous_release}")."
}

require_safe_root
prepare_directories
require_docker
require_environment

exec 9>"${SHARED_DIR}/deploy.lock"
if ! flock -n 9; then
  echo "Ya existe otra operacion de despliegue en curso." >&2
  exit 1
fi

case "${ACTION}" in
  deploy)
    deploy_release
    ;;
  status)
    show_status
    ;;
  rollback)
    rollback_release
    ;;
  *)
    usage
    exit 2
    ;;
esac
