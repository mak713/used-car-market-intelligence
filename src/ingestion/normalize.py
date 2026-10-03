"""Row normalization: only enough to get keys, timestamps, a deterministic hash and a JSON payload."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np
import pyarrow as pa

from src.ingestion.contract import PLACEHOLDER


def null_placeholders(value):
    """Premium/redacted placeholder -> None (mirrors the dbt staging macro)."""
    return None if value == PLACEHOLDER else value


def _jsonable(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    if isinstance(v, (float, np.floating)):
        if v != v:  # NaN
            return None
        return float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def canonical_json(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(record: dict) -> str:
    """Deterministic sha256 over the canonical JSON of the normalized record."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RawRow:
    primary_key: str
    listing_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    record_hash: str
    payload_json: str


def _float32_columns(table: pa.Table) -> set[str]:
    return {f.name for f in table.schema if pa.types.is_float32(f.type)}


def table_to_rows(table: pa.Table) -> list[RawRow]:
    f32 = _float32_columns(table)
    cols = {name: table[name].to_pylist() for name in table.column_names}
    rows = []
    for i in range(table.num_rows):
        rec = {}
        for name, values in cols.items():
            v = values[i]
            if name in f32 and v is not None:
                v = float(str(np.float32(v)))  # shortest float32 repr, e.g. 2.7 not 2.700000047
            rec[name] = _jsonable(v)
        rows.append(RawRow(
            primary_key=rec["_primaryKey"],
            listing_id=rec["listingId"],
            first_seen_at=cols["_firstSeenAt"][i],
            last_seen_at=cols["_lastSeenAt"][i],
            record_hash=record_hash(rec),
            payload_json=canonical_json(rec),
        ))
    return rows


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.parquet$")


def partition_date(filename: str) -> date:
    m = _DATE_RE.search(filename)
    if not m:
        raise ValueError(f"cannot infer partition date from filename: {filename}")
    return date.fromisoformat(m.group(1))
