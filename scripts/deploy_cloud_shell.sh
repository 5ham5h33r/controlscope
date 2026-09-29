#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?Usage: scripts/deploy_cloud_shell.sh PROJECT_ID [DATASET]}"
DATASET="${2:-controlscope}"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[cloud]"

controlscope demo
controlscope verify
controlscope upload-bigquery --project "$PROJECT_ID" --dataset "$DATASET"

mkdir -p data/dbt-profiles
cat > data/dbt-profiles/profiles.yml <<EOF
controlscope:
  target: cloud
  outputs:
    cloud:
      type: bigquery
      method: oauth
      project: $PROJECT_ID
      dataset: $DATASET
      threads: 4
      location: US
EOF

dbt seed --profiles-dir data/dbt-profiles
dbt run --profiles-dir data/dbt-profiles
dbt test --profiles-dir data/dbt-profiles
controlscope publish-bigquery --project "$PROJECT_ID" --dataset "$DATASET"

echo "Published ControlScope to $PROJECT_ID.$DATASET"
