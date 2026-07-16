#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

DEPLOY_ROOT="${1:-${HOME}/apps/prototipo-mamografia}"
DEPLOY_ROOT="$(realpath -m "${DEPLOY_ROOT}")"
SHARED_DIR="${DEPLOY_ROOT}/shared"
RUNTIME_DIR="${SHARED_DIR}/runtime"

case "${DEPLOY_ROOT}" in
  "${HOME}"/*)
    ;;
  *)
    echo "El directorio debe estar dentro de ${HOME}." >&2
    exit 1
    ;;
esac

if ! docker info >/dev/null 2>&1; then
  echo "El usuario actual no puede acceder al daemon de Docker." >&2
  exit 1
fi

mkdir -p "${DEPLOY_ROOT}/releases" "${RUNTIME_DIR}"
chmod 700 "${DEPLOY_ROOT}" "${SHARED_DIR}" "${RUNTIME_DIR}"

echo "Directorio aislado preparado: ${DEPLOY_ROOT}"
echo "Siguiente paso: crear ${SHARED_DIR}/.env.production con permisos 600."
echo "No se modificaron ni reiniciaron contenedores existentes."
