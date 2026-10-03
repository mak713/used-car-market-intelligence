"""meta.pipeline_runs / meta.processed_files bookkeeping."""
from __future__ import annotations

import uuid

import psycopg

from src.ingestion.source import SourceFile


def start_run(conn: psycopg.Connection, source_revision: str | None = None) -> uuid.UUID:
    run_id = uuid.uuid4()
    conn.execute("INSERT INTO meta.pipeline_runs (run_id, source_revision) VALUES (%s, %s)",
                 (run_id, source_revision))
    conn.commit()
    return run_id


def update_run(conn: psycopg.Connection, run_id: uuid.UUID, **fields) -> None:
    """Set columns on a run row (counters, dbt_status, ...). Keys are trusted column names."""
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    conn.execute(f"UPDATE meta.pipeline_runs SET {sets} WHERE run_id = %s", (*fields.values(), run_id))
    conn.commit()


def finish_run(conn: psycopg.Connection, run_id: uuid.UUID, status: str,
               error_summary: str | None = None, **fields) -> None:
    update_run(conn, run_id, status=status, error_summary=error_summary, **fields)
    conn.execute("UPDATE meta.pipeline_runs SET finished_at = now() WHERE run_id = %s", (run_id,))
    conn.commit()


def processed_keys(conn: psycopg.Connection) -> set[tuple[str, str]]:
    return set(conn.execute("SELECT source_file, content_hash FROM meta.processed_files").fetchall())


def select_unprocessed(files: list[SourceFile], done: set[tuple[str, str]]) -> list[SourceFile]:
    """Unseen or changed files. A file with an unknown hash can't be ruled out, so it is kept."""
    return [f for f in files if f.content_hash is None or (f.name, f.content_hash) not in done]
