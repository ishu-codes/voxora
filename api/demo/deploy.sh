#!/usr/bin/env bash
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "No Google Cloud project is configured. Run:"
  echo "  gcloud auth login"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  echo "  gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com"
  echo "  demo/deploy.sh"
  exit 1
fi

if ! gcloud auth print-access-token >/dev/null 2>&1; then
  echo "Authenticate first with: gcloud auth login"
  exit 1
fi

SERVICE="${DEMO_SERVICE:-voxora-bench-demo}"
REGION="${DEMO_REGION:-asia-south1}"
IMAGE="gcr.io/${PROJECT}/${SERVICE}:$(date +%Y%m%d%H%M%S)"

gcloud builds submit --tag "${IMAGE}" --file demo/Dockerfile .
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --timeout 300 \
  --set-secrets "DEMO_CODE=demo-code:latest,SARVAM_API_KEY=sarvam-api-key:latest,LLM_API_KEY=llm-api-key:latest" \
  --set-env-vars "LLM_BASE_URL=${LLM_BASE_URL},LLM_MODEL=${LLM_MODEL},DEMO_SESSIONS_PER_IP_HOUR=${DEMO_SESSIONS_PER_IP_HOUR:-5},DEMO_DAILY_SESSION_CAP=${DEMO_DAILY_SESSION_CAP:-100}"
