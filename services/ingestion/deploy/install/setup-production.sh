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
DATABASE_URL=postgresql+asyncpg://ingestion:ingestion@localhost:5432/ingestion

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=ingestion.documents

# MinIO
MINIO_URL=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Vault
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Tika
TIKA_URL=http://localhost:9998
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

echo "========================================================="
echo "Setup Complete!"
echo "Manual steps needed:"
echo "1. Install PostgreSQL, MinIO, Kafka, Vault, Tika, ELK separately."
echo "2. Edit /etc/ingestion/ingestion.env with production secrets."
echo "3. Run 'systemctl start ingestion-api' to start services."
echo "NOTE: Ensure you have backup strategies for PostgreSQL and MinIO."
echo "========================================================="
