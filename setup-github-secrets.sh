#!/bin/bash
set -e

REPO="b3661555-stack/revue-reels-ig"

echo "=== GitHub Secrets Setup for $REPO ==="
echo ""

# Load from .env if exists
if [ -f .env ]; then
    echo "Loading secrets from .env..."
    set -a
    source .env
    set +a
else
    echo "Error: .env file not found. Copy from .env.example and fill in values."
    exit 1
fi

# Push each secret
declare -a SECRETS=(
    "GOOGLE_AI_STUDIO_API_KEY"
    "UNSPLASH_API_KEY"
    "AZURE_TTS_KEY"
    "AZURE_TTS_REGION"
    "INSTAGRAM_USERNAME"
    "INSTAGRAM_PASSWORD"
    "PUBMED_EMAIL"
)

for SECRET in "${SECRETS[@]}"; do
    VALUE="${!SECRET}"
    if [ -z "$VALUE" ]; then
        echo "⚠️  $SECRET is empty, skipping"
    else
        gh secret set "$SECRET" --body "$VALUE" -R "$REPO"
        echo "✓ $SECRET"
    fi
done

echo ""
echo "=== OK ==="
