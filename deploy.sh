#!/usr/bin/env bash
set -euo pipefail

# 0. Check ADMIN_KEY argument or environment variable
ADMIN_KEY="${1:-${ADMIN_KEY:-}}"

if [ -z "${ADMIN_KEY}" ]; then
  echo "=========================================="
  echo " ERROR: ADMIN_KEY is required for deployment!"
  echo "=========================================="
  echo "Usage: $0 <ADMIN_KEY>"
  echo "   or: ADMIN_KEY=\"your_key\" $0"
  echo ""
  echo "예시: ./deploy.sh \"MySecret123!\""
  exit 1
fi

# Configuration
APP_NAME="${APP_NAME:-automotive-newsletter}"
IMAGE_NAME="${IMAGE_NAME:-automotive-newsletter:latest}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${PROJECT_DIR}/data"
TIMEZONE="${TZ:-${NEWSLETTER_TIMEZONE:-Europe/Berlin}}"
COLLECTION_TIME="${DAILY_COLLECTION_TIME:-06:00}"

echo "=========================================="
echo " Starting deployment: ${APP_NAME}"
echo " Schedule: daily at ${COLLECTION_TIME} (${TIMEZONE})"
echo "=========================================="

cd "${PROJECT_DIR}"

# 1. Ensure data directory exists for volume mounting
mkdir -p "${DATA_DIR}"

# 2. Pull latest changes from git
echo ">>> Pulling latest changes from git..."
git pull

# 3. Build Docker image
echo ">>> Building Docker image: ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

# 4. Stop existing container if running
if [ "$(docker ps -q -f name=^/${APP_NAME}$)" ]; then
  echo ">>> Stopping existing container '${APP_NAME}'..."
  docker stop "${APP_NAME}"
fi

# 5. Remove existing container if present
if [ "$(docker ps -aq -f name=^/${APP_NAME}$)" ]; then
  echo ">>> Removing existing container '${APP_NAME}'..."
  docker rm "${APP_NAME}"
fi

# 6. Run new container
echo ">>> Starting new container '${APP_NAME}' on 127.0.0.1:8000..."
docker run -d \
  --name "${APP_NAME}" \
  -p 127.0.0.1:8000:8000 \
  -v "${DATA_DIR}:/app/data" \
  -e ENABLE_DAILY_SCHEDULER=true \
  -e DAILY_COLLECTION_TIME="${COLLECTION_TIME}" \
  -e TZ="${TIMEZONE}" \
  -e NEWSLETTER_TIMEZONE="${TIMEZONE}" \
  -e ADMIN_KEY="${ADMIN_KEY}" \
  --restart unless-stopped \
  "${IMAGE_NAME}"

# 7. Verification
echo ">>> Verifying container status..."
sleep 2

if [ "$(docker ps -q -f name=^/${APP_NAME}$)" ]; then
  echo "=========================================="
  echo " Deployment successful!"
  echo " App running at: http://127.0.0.1:8000"
  echo " Container status:"
  docker ps -f name=^/${APP_NAME}$
  echo "=========================================="
else
  echo "=========================================="
  echo " ERROR: Container failed to start!"
  echo " Container logs:"
  docker logs "${APP_NAME}"
  echo "=========================================="
  exit 1
fi

