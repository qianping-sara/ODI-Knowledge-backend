#!/usr/bin/env bash
set -euo pipefail

container_app_name="${CONTAINER_APP_NAME:?CONTAINER_APP_NAME is required}"
resource_group="${RESOURCE_GROUP_NAME:?RESOURCE_GROUP_NAME is required}"
image_ref="${IMAGE_REF:?IMAGE_REF is required}"
revision_suffix="${REVISION_SUFFIX:?REVISION_SUFFIX is required}"

echo "Setting secrets for Container App ${container_app_name}"
az containerapp secret set \
  --name "${container_app_name}" \
  --resource-group "${resource_group}" \
  --secrets \
    azure-openai-api-key="${AZURE_OPENAI_API_KEY}" \
    mysql-password="${MYSQL_PASSWORD}" \
    tavily-api-key="${TAVILY_API_KEY}"

echo "Deploying image ${image_ref} to Container App ${container_app_name}"
az containerapp update \
  --name "${container_app_name}" \
  --resource-group "${resource_group}" \
  --image "${image_ref}" \
  --revision-suffix "${revision_suffix}" \
  --set-env-vars \
    APP_NAME="${APP_NAME}" \
    AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
    AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION}" \
    AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT}" \
    MYSQL_HOST="${MYSQL_HOST}" \
    MYSQL_DB="${MYSQL_DB}" \
    MYSQL_PORT="${MYSQL_PORT}" \
    MYSQL_USER="${MYSQL_USER}" \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key \
    MYSQL_PASSWORD=secretref:mysql-password \
    TAVILY_API_KEY=secretref:tavily-api-key \
  --output none

echo "Container App update completed."
