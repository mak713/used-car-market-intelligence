import json
from datetime import date

import pytest

from src.ingestion.normalize import (null_placeholders, partition_date, record_hash, table_to_rows)
from tests.fixtures.synthetic import make_row, make_table


def test_hash_is_deterministic_and_order_independent():
    a = {"x": 1, "y": [1, 2], "z": None}
    b = {"z": None, "y": [1, 2], "x": 1}
    assert record_hash(a) == record_hash(b)
    assert record_hash(a) != record_hash({**a, "x": 2})


def test_same_rows_same_hash_across_calls():
    t = make_table([make_row(i) for i in range(5)])
    assert [r.record_hash for r in table_to_rows(t)] == [r.record_hash for r in table_to_rows(t)]


def test_changed_field_changes_hash():
    h1 = table_to_rows(make_table([make_row(1)]))[0].record_hash
    h2 = table_to_rows(make_table([make_row(1, mileage=99999)]))[0].record_hash
    assert h1 != h2


def test_payload_is_json_with_clean_types():
    r = table_to_rows(make_table([make_row(1, trim=None)]))[0]
    p = json.loads(r.payload_json)
    assert p["displacementUOM"] == 2.7           # float32 shortest repr, not 2.700000047...
    assert p["trim"] is None and p["_firstSeenAt"].endswith("+00:00")
    assert p["vin"] == "[PREMIUM]"               # raw layer keeps source fidelity
    assert r.primary_key == "pk000001" and r.listing_id == "L000001"


def test_premium_placeholder_normalization():
    assert null_placeholders("[PREMIUM]") is None
    assert null_placeholders("Toyota") == "Toyota"
    assert null_placeholders(None) is None


def test_partition_date():
    assert partition_date("2026-08-21.parquet") == date(2026, 8, 21)
    with pytest.raises(ValueError):
        partition_date("latest.parquet")
