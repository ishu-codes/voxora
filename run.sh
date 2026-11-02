#!/usr/bin/env bash
set -e

REGION=asia-south1

PROJECT_ID=voxora-prod
PROJECT_NUMBER=1015171053097
REPO=voxora

# TAG=20261030174355
TAG=latest


API_SA=voxora-api-run@${PROJECT_ID}.iam.gserviceaccount.com
WEB_SA=voxora-web-run@${PROJECT_ID}.iam.gserviceaccount.com
CB_SA=${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com



case "$1" in
    'service-accounts-create')

    ;;

    'secrets-create')
        read -rsp "Sarvam API key: " SARVAM_KEY
        echo
        printf '%s' "$SARVAM_KEY" | gcloud secrets create voxora-sarvam-api-key \
          --replication-policy=automatic \
          --data-file=-
        unset SARVAM_KEY

        read -rsp "LLM API key: " LLM_KEY
        echo
        printf '%s' "$LLM_KEY" | gcloud secrets create voxora-llm-api-key \
          --replication-policy=automatic \
          --data-file=-
        unset LLM_KEY

        openssl rand -hex 48 | gcloud secrets create voxora-rate-limit-secret \
          --replication-policy=automatic \
          --data-file=-

    ;;

    'grant-api-runtime-account-access')
        for SECRET in $(gcloud secrets list --format="value(name)")
        do
            gcloud secrets add-iam-policy-binding "$SECRET" \
                --member="serviceAccount:${API_SA}" \
                --role="roles/secretmanager.secretAccessor" \
                --quiet
        done
    ;;

    'object-storage-permission')
        gcloud storage buckets add-iam-policy-binding \
          gs://${PROJECT_ID}_cloudbuild \
          --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
          --role="roles/storage.objectViewer"

        gcloud artifacts repositories add-iam-policy-binding voxora \
          --location="$REGION" \
          --project="$PROJECT_ID" \
          --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
          --role="roles/artifactregistry.writer"


        gcloud projects add-iam-policy-binding $PROJECT_ID \
          --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
          --role="roles/logging.logWriter"
    ;;

    'api-build')
        API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:${TAG}"
        gcloud builds submit api \
          --tag "$API_IMAGE" \
          --timeout=30m
    ;;

    'api-deploy')
        API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:${TAG}"

        gcloud run deploy voxora-api \
          --image "$API_IMAGE" \
          --region "$REGION" \
          --platform managed \
          --service-account "$API_SA" \
          --port 8000 \
          --allow-unauthenticated \
          --cpu 1 \
          --memory 1Gi \
          --concurrency 20 \
          --min-instances 1 \
          --max-instances 1 \
          --timeout 1200 \
          --env-vars-file ./infra/env/voxora-api.env.yaml \
          --set-secrets "SARVAM_API_KEY=voxora-sarvam-api-key:latest,LLM_API_KEY=voxora-llm-api-key:latest,RATE_LIMIT_SECRET=voxora-rate-limit-secret:latest"
    ;;

    'web-build')
        WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/web:${TAG}"
        API_URL=$(gcloud run services describe voxora-api --region "$REGION" --format="value(status.url)")

        gcloud builds submit web \
            --config=./infra/env/voxora-cloudbuild-web.yaml \
            --substitutions="_API_URL=${API_URL},_IMAGE=${WEB_IMAGE}"
    ;;

    'web-deploy')
        WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/web:${TAG}"

        gcloud run deploy voxora-web \
          --image "$WEB_IMAGE" \
          --region "$REGION" \
          --platform managed \
          --service-account "$WEB_SA" \
          --port 3000 \
          --allow-unauthenticated \
          --cpu 1 \
          --memory 512Mi \
          --concurrency 80 \
          --min-instances 0 \
          --max-instances 3 \
          --timeout 60

        WEB_URL=$(gcloud run services describe voxora-web --region "$REGION" --format="value(status.url)")
        gcloud run services update voxora-api \
          --region "$REGION" \
          --update-env-vars "CORS_ORIGINS=${WEB_URL}"
    ;;

    *)
        echo "Usage: $0 {start|stop}"
        exit 1
    ;;
esac
