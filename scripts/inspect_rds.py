"""Read-only inventory before planning an integration upgrade of a shared RDS DB."""
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql


def main():
    # Optional local file for inspection only; never print its values.
    path = Path(os.environ.get("RDS_INSPECTION_ENV", ".integration/rds.env"))
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value.strip().strip('"\''))
    conn = psycopg2.connect(host=os.environ["AWS_RDS_HOST"],
                            port=os.environ.get("AWS_RDS_PORT", "5432"),
                            user=os.environ["AWS_RDS_USER"],
                            password=os.environ["AWS_RDS_PASSWORD"],
                            dbname=os.environ["AWS_RDS_DB"],
                            sslmode=os.environ.get("AWS_RDS_SSLMODE", "require"),
                            connect_timeout=10, options="-c default_transaction_read_only=on -c statement_timeout=10000")
    conn.set_session(readonly=True)
    result = {}
    with conn, conn.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user, current_setting('transaction_read_only')")
        result["connection"] = cursor.fetchone()
        cursor.execute("SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
        result["tls"] = cursor.fetchone()
        cursor.execute("SELECT table_schema,table_name FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2")
        tables = cursor.fetchall()
        result["tables"] = tables
        result["migration_ledgers"] = {}
        for schema, table in tables:
            if "alembic" in table or "migration" in table:
                cursor.execute(sql.SQL("SELECT * FROM {}.{} LIMIT 30").format(sql.Identifier(schema), sql.Identifier(table)))
                result["migration_ledgers"][f"{schema}.{table}"] = cursor.fetchall()
        cursor.execute("SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,ordinal_position")
        result["columns"] = cursor.fetchall()
        cursor.execute("SELECT schemaname,relname,n_live_tup FROM pg_stat_user_tables ORDER BY 1,2")
        result["estimated_row_counts"] = cursor.fetchall()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
