"""Apply idempotent DDL (schemas, meta tables, raw table)."""
from __future__ import annotations

from pathlib import Path

import psycopg

DDL_DIR = Path(__file__).parent / "ddl"


def apply_ddl(conn: psycopg.Connection) -> None:
    for f in sorted(DDL_DIR.glob("*.sql")):
        conn.execute(f.read_text())
    conn.commit()


if __name__ == "__main__":
    from src.db.config import connect

    with connect() as c:
        apply_ddl(c)
    print("DDL applied")
