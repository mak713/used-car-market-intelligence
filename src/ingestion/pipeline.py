"""Ingestion steps shared by the CLI and the Prefect flow.

discover -> select unprocessed -> download -> validate (all files, before any write) -> load.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import psycopg
import pyarrow.parquet as pq

from src.ingestion import runs
from src.ingestion.contract import ContractError, redaction_report, validate_table
from src.ingestion.loader import LoadResult, load_file
from src.ingestion.source import SourceFile, discover_hub, discover_local, download_hub

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw"


def discover(source_dir: Path | None = None, revision: str | None = None,
             date_from: date | None = None, date_to: date | None = None):
    if source_dir:
        return discover_local(source_dir, date_from, date_to)
    return discover_hub(revision, date_from, date_to)


def download(files: list[SourceFile], source_dir: Path | None = None,
             data_dir: Path = DEFAULT_DATA_DIR) -> None:
    if not source_dir:
        download_hub(files, data_dir)


def validate(files: list[SourceFile]) -> dict[str, dict]:
    """Validate every file; raise one ContractError listing all failures. Writes nothing."""
    failures, report = [], {}
    for f in files:
        try:
            table = pq.read_table(f.local_path)
            validate_table(table, f.name)
            report[f.name] = {"rows": table.num_rows, "redacted": redaction_report(table)}
        except ContractError as e:
            failures.append(str(e))
        except Exception as e:  # unreadable/corrupt parquet
            failures.append(f"{f.name}: unreadable parquet ({type(e).__name__}: {e})")
    if failures:
        raise ContractError(" | ".join(failures))
    return report


@dataclass
class IngestTotals:
    files_processed: int = 0
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_unchanged: int = 0
    per_file: dict[str, LoadResult] = field(default_factory=dict)

    def add(self, name: str, r: LoadResult) -> None:
        self.files_processed += 1
        self.rows_read += r.rows_read
        self.rows_inserted += r.rows_inserted
        self.rows_updated += r.rows_updated
        self.rows_unchanged += r.rows_unchanged
        self.per_file[name] = r


def load(conn: psycopg.Connection, files: list[SourceFile], run_id: uuid.UUID,
         totals: IngestTotals | None = None) -> IngestTotals:
    """Load files in date order, one transaction each. Stops at the first failing file;
    earlier files stay committed, the failing one rolls back and is not checkpointed."""
    totals = totals if totals is not None else IngestTotals()
    for f in sorted(files, key=lambda x: (x.partition_date, x.name)):
        totals.add(f.name, load_file(conn, f, pq.read_table(f.local_path), run_id))
    return totals


def ingest(conn: psycopg.Connection, source_dir: Path | None = None, revision: str | None = None,
           date_from: date | None = None, date_to: date | None = None,
           data_dir: Path = DEFAULT_DATA_DIR) -> tuple[uuid.UUID, IngestTotals]:
    """Whole ingestion as a single call (CLI / tests). Records the run in meta.pipeline_runs."""
    resolved_rev, files = discover(source_dir, revision, date_from, date_to)
    run_id = runs.start_run(conn, resolved_rev)
    totals = IngestTotals()
    try:
        todo = runs.select_unprocessed(files, runs.processed_keys(conn))
        download(todo, source_dir, data_dir)
        todo = runs.select_unprocessed(todo, runs.processed_keys(conn))  # re-check once hashes are known
        runs.update_run(conn, run_id, files_discovered=len(files))
        validate(todo)
        load(conn, todo, run_id, totals)
    except Exception as e:
        runs.finish_run(conn, run_id, "failed", f"{type(e).__name__}: {e}"[:2000],
                        files_processed=totals.files_processed, rows_read=totals.rows_read,
                        rows_inserted=totals.rows_inserted, rows_updated=totals.rows_updated,
                        rows_unchanged=totals.rows_unchanged)
        raise
    runs.finish_run(conn, run_id, "success", None, files_processed=totals.files_processed,
                    rows_read=totals.rows_read, rows_inserted=totals.rows_inserted,
                    rows_updated=totals.rows_updated, rows_unchanged=totals.rows_unchanged)
    return run_id, totals
