"""
PostgreSQL Database Auto-Initialization & Verification Script.
Connects to local PostgreSQL instance and ensures the target database exists.
"""
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB


def setup_postgres():
    print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT} as user '{POSTGRES_USER}'...")
    try:
        # Connect to the default 'postgres' database to check/create target database
        conn = psycopg2.connect(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if target database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (POSTGRES_DB,))
        exists = cursor.fetchone()

        if not exists:
            print(f"Creating PostgreSQL database '{POSTGRES_DB}'...")
            cursor.execute(f'CREATE DATABASE "{POSTGRES_DB}";')
            print(f"[SUCCESS] Database '{POSTGRES_DB}' created successfully!")
        else:
            print(f"[INFO] Database '{POSTGRES_DB}' already exists.")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to configure PostgreSQL: {e}")
        return False


if __name__ == "__main__":
    setup_postgres()
