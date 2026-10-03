"""Atomic per-file raw load with record-level upsert."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg
import pyarrow as pa

from src.ingestion.normalize import table_to_rows
from src.ingestion.source import SourceFile

# Update only when the record actually changed AND the incoming observation is not older than the
# stored one (a stale revision must never overwrite a newer observation). Identical records no-op.
_UPSERT = """
INSERT INTO raw.autotrader_records AS t
    (primary_key, listing_id, first_seen_at, last_seen_at, source_file, source_file_date,
     record_hash, payload)
SELECT primary_key, listing_id, first_seen_at, last_seen_at, %(file)s, %(fdate)s, record_hash,
       payload::jsonb
FROM _stg
ON CONFLICT (primary_key) DO UPDATE SET
    listing_id       = EXCLUDED.listing_id,
    first_seen_at    = LEAST(t.first_seen_at, EXCLUDED.first_seen_at),
    last_seen_at     = EXCLUDED.last_seen_at,
    source_file      = EXCLUDED.source_file,
    source_file_date = EXCLUDED.source_file_date,
    record_hash      = EXCLUDED.record_hash,
    payload          = EXCLUDED.payload,
    updated_at       = now()
WHERE t.record_hash IS DISTINCT FROM EXCLUDED.record_hash
  AND EXCLUDED.last_seen_at >= t.last_seen_at
RETURNING (xmax = 0) AS inserted
"""


@dataclass
class LoadResult:
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_unchanged: int


def load_file(conn: psycopg.Connection, sf: SourceFile, table: pa.Table,
              run_id: uuid.UUID | None = None) -> LoadResult:
    """Load one file in a single transaction; on any error nothing (incl. the checkpoint) is kept."""
    rows = table_to_rows(table)
    with conn.transaction():
        conn.execute("""CREATE TEMP TABLE _stg (primary_key text, listing_id text,
                        first_seen_at timestamptz, last_seen_at timestamptz,
                        record_hash text, payload text) ON COMMIT DROP""")
        with conn.cursor() as cur:
            with cur.copy("COPY _stg FROM STDIN") as cp:
                for r in rows:
                    cp.write_row((r.primary_key, r.listing_id, r.first_seen_at, r.last_seen_at,
                                  r.record_hash, r.payload_json))
            cur.execute(_UPSERT, {"file": sf.name, "fdate": sf.partition_date})
            flags = [x[0] for x in cur.fetchall()]
        ins, upd = sum(flags), len(flags) - sum(flags)
        res = LoadResult(len(rows), ins, upd, len(rows) - ins - upd)
        conn.execute(
            """INSERT INTO meta.processed_files
               (source_file, content_hash, source_file_date, source_revision, row_count,
                rows_inserted, rows_updated, rows_unchanged, pipeline_run_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (sf.name, sf.content_hash, sf.partition_date, sf.revision, res.rows_read,
             res.rows_inserted, res.rows_updated, res.rows_unchanged, run_id))
    return res
