"""python -m src.ingestion.cli [--source-dir D] [--revision SHA] [--date-from D] [--date-to D]"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.db.bootstrap import apply_ddl
from src.db.config import connect
from src.ingestion.pipeline import ingest


def main() -> None:
    ap = argparse.ArgumentParser(description="Incremental raw ingestion")
    ap.add_argument("--source-dir", type=Path, help="local partition directory instead of Hugging Face")
    ap.add_argument("--revision", help="pin the Hugging Face repo revision (default: current)")
    ap.add_argument("--date-from", type=date.fromisoformat)
    ap.add_argument("--date-to", type=date.fromisoformat)
    a = ap.parse_args()
    with connect() as conn:
        apply_ddl(conn)
        run_id, t = ingest(conn, a.source_dir, a.revision, a.date_from, a.date_to)
    print(f"run {run_id}: files={t.files_processed} read={t.rows_read} inserted={t.rows_inserted} "
          f"updated={t.rows_updated} unchanged={t.rows_unchanged}")


if __name__ == "__main__":
    main()
