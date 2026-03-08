#!/usr/bin/env bash
set -euo pipefail

container_registry="${containerRegistry:?containerRegistry is required}"
image_repository="${imageRepository:?imageRepository is required}"
tag="${tag:?tag is required}"

mysql_host="${MYSQL_HOST:-}"
mysql_port="${MYSQL_PORT:-3306}"
mysql_user="${MYSQL_USER:-}"
mysql_password="${MYSQL_PASSWORD:-}"
mysql_db="${MYSQL_DB:-}"

if [[ -z "${mysql_host}" || -z "${mysql_user}" || -z "${mysql_password}" || -z "${mysql_db}" ]]; then
  echo "Missing required database environment variables; ensure MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DB are set."
  exit 1
fi

image_ref="${container_registry}/${image_repository}:${tag}"
acr_name="${container_registry%%.*}"

echo "Logging into Azure Container Registry ${acr_name}"
az acr login --name "${acr_name}" --output none

echo "Pulling image ${image_ref} for migrations"
docker pull "${image_ref}"

echo "Applying database migrations with alembic upgrade head (with debug tracing)"
if ! docker run --rm \
  --entrypoint "" \
  -e MYSQL_HOST="${mysql_host}" \
  -e MYSQL_PORT="${mysql_port}" \
  -e MYSQL_USER="${mysql_user}" \
  -e MYSQL_PASSWORD="${mysql_password}" \
  -e MYSQL_DB="${mysql_db}" \
  "${image_ref}" \
  bash -c "set -euo pipefail; cd /app; set -x; ALEMBIC_LOG_LEVEL=INFO alembic upgrade head"; then
  echo "Alembic migration failed; see output above for details."
  exit 1
fi
