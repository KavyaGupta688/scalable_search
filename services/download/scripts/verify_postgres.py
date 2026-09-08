"""
Verification script to inspect AWS RDS / PostgreSQL connection, schema, and live records.
"""
import sys
from pathlib import Path
import psycopg2

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    AWS_RDS_HOST,
    AWS_RDS_PORT,
    AWS_RDS_USER,
    AWS_RDS_PASSWORD,
    AWS_RDS_DB,
    AWS_RDS_SSLMODE,
    DATABASE_URL
)
from database.db import db


def inspect_postgres():
    print("=" * 65)
    print("DATABASE LIVE INTEGRATION STATUS (AWS RDS / POSTGRESQL)")
    print("=" * 65)
    
    is_rds = "rds.amazonaws.com" in AWS_RDS_HOST
    target_type = "AWS RDS PostgreSQL" if is_rds else "PostgreSQL"
    
    print(f"Target Database:   {target_type}")
    print(f"Host & Port:       {AWS_RDS_HOST}:{AWS_RDS_PORT}")
    print(f"Database Name:     {AWS_RDS_DB}")
    print(f"Username:          {AWS_RDS_USER}")
    print(f"SSL Mode:          {AWS_RDS_SSLMODE}")
    print("-" * 65)

    try:
        conn_kwargs = {
            "user": AWS_RDS_USER,
            "password": AWS_RDS_PASSWORD,
            "host": AWS_RDS_HOST,
            "port": int(AWS_RDS_PORT),
            "dbname": AWS_RDS_DB,
            "connect_timeout": 10
        }
        if is_rds:
            conn_kwargs["sslmode"] = AWS_RDS_SSLMODE

        conn = psycopg2.connect(**conn_kwargs)
        cur = conn.cursor()

        print(f"Connection Status: [CONNECTED & ACTIVE]")
        print("-" * 65)

        # Get tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        tables = [t[0] for t in cur.fetchall()]
        print(f"Tables Created ({len(tables)}):")

        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            cnt = cur.fetchone()[0]
            print(f"   * {table:<25} -> {cnt} records")

        print("-" * 65)
        # Show sample records from forensic_audit_logs if present
        if "forensic_audit_logs" in tables:
            cur.execute("SELECT download_id, user_id, user_email, s3_key, iso_timestamp, status FROM forensic_audit_logs ORDER BY timestamp DESC LIMIT 3")
            rows = cur.fetchall()
            if rows:
                print("Recent Forensic Audit Logs:")
                for r in rows:
                    print(f"   - [{r[4][:19] if r[4] else 'N/A'}] User: {r[1]} ({r[2]}) | S3: {r[3]} | Status: {r[5]}")
            else:
                print("No audit logs in database yet.")

        cur.close()
        conn.close()
        print("=" * 65)
        print(f"[SUCCESS] {target_type} is 100% connected, schema initialized & active!")
        print("=" * 65)
        return True
    except Exception as e:
        print(f"[ERROR] Connection Failed: {e}")
        print("\nTroubleshooting Tips:")
        print("1. Check Security Group in AWS Console: Ensure inbound rule allows TCP port 5432 from your IP.")
        print("2. Ensure the RDS instance has 'Publicly Accessible' set to Yes (if connecting from local PC).")
        print("3. Check credentials and database name in .env.")
        print("=" * 65)
        return False


if __name__ == "__main__":
    inspect_postgres()
