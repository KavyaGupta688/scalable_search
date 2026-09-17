#!/bin/bash
set -e

echo "Setting up Data Ingestion Module production environment..."

# 1. Create user and group
if ! getent group ingestion > /dev/null 2>&1; then
    groupadd --system ingestion
fi
if ! getent passwd ingestion > /dev/null 2>&1; then
    useradd --system --gid ingestion --no-create-home --shell /bin/false ingestion
fi

# 2. Install dependencies
apt-get update
apt-get install -y python3.11 python3.11-venv libmagic1 curl

# 3. Create app directory
mkdir -p /opt/ingestion
chown ingestion:ingestion /opt/ingestion

# 4. Create virtualenv
python3.11 -m venv /opt/ingestion/venv
/opt/ingestion/venv/bin/pip install --upgrade pip
# Assuming current dir contains pyproject.toml
/opt/ingestion/venv/bin/pip install .

chown -R ingestion:ingestion /opt/ingestion/venv

# 5. Create config directory
mkdir -p /etc/ingestion

cat > /etc/ingestion/ingestion.env << 'EOF'
# Environment variables for Data Ingestion Module

# App settings
APP_ENVIRONMENT=production
APP_DEBUG=false

# Database
DB_HOST=database.internal
DB_PORT=5432
DB_NAME=ingestion
DB_USER=ingestion
DB_PASSWORD=replace-from-secret-manager

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_INGESTION_TOPIC=ingestion-jobs
KAFKA_DEAD_LETTER_TOPIC=ingestion-dead-letter
KAFKA_AI_PROCESSING_TOPIC=ai-processing-events

# Vault
VAULT_URL=http://localhost:8200
VAULT_TOKEN=replace-from-secret-manager

# Licence-expiry status reconciliation. It never deletes vendor content.
RETENTION_ENABLED=true
RETENTION_DRY_RUN=true
RETENTION_POLICY_YEARS=3
RETENTION_RECONCILIATION_INTERVAL_SECONDS=900
RETENTION_RECONCILIATION_BATCH_SIZE=500
RETENTION_METRICS_PORT=9200

# Vendor metadata files
METADATA_REQUIRED=true
METADATA_MAX_FILE_BYTES=33554432
METADATA_CACHE_MAX_DIRECTORIES=1000
METADATA_MANIFEST_NAMES=metadata.csv,metadata11.csv
METADATA_SIDECAR_NAMES=.id,.desc,.tags,.lab,.cate
METADATA_SIDECARS_WITH_MANIFEST=false
METADATA_ADDITIONAL_METADATA_MAX_KEYS=64
METADATA_ADDITIONAL_METADATA_MAX_BYTES=65536
EOF

chmod 600 /etc/ingestion/ingestion.env
chown ingestion:ingestion /etc/ingestion/ingestion.env

# 6. Copy systemd files
cp deploy/systemd/*.service /etc/systemd/system/
cp deploy/systemd/*.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable ingestion-api.service
systemctl enable ingestion-worker.service
systemctl enable ingestion-reconciliation.timer
systemctl enable ingestion-retention.service

echo "========================================================="
echo "Setup Complete!"
echo "Manual steps needed:"
echo "1. Install PostgreSQL, Kafka, Vault, and ELK separately."
echo "2. Edit /etc/ingestion/ingestion.env with production secrets."
echo "3. Run 'systemctl start ingestion-api' to start services."
echo "NOTE: Back up PostgreSQL and verify vendor-source availability separately."
echo "========================================================="
