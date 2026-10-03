import pytest

from src.ingestion.contract import ContractError
from src.ingestion.pipeline import ingest
from tests.fixtures.synthetic import make_row, write_partition

pytestmark = pytest.mark.integration


def counts(conn):
    return (conn.execute("select count(*) from raw.autotrader_records").fetchone()[0],
            conn.execute("select count(*) from meta.processed_files").fetchone()[0])


def rows(start, n, **over):
    return [make_row(i, **over) for i in range(start, start + n)]


def test_new_file_processing_and_identical_rerun_is_noop(conn, tmp_path):
    write_partition(tmp_path, "2026-09-01", rows(0, 10))
    write_partition(tmp_path, "2026-09-02", rows(10, 10))
    _, t = ingest(conn, tmp_path)
    assert (t.files_processed, t.rows_inserted) == (2, 20)
    assert counts(conn) == (20, 2)
    before = conn.execute("select md5(string_agg(primary_key||record_hash||updated_at::text, ',' order by primary_key)) from raw.autotrader_records").fetchone()
    _, t2 = ingest(conn, tmp_path)                      # no-change rerun
    assert t2.files_processed == 0 and t2.rows_read == 0
    assert counts(conn) == (20, 2)
    after = conn.execute("select md5(string_agg(primary_key||record_hash||updated_at::text, ',' order by primary_key)) from raw.autotrader_records").fetchone()
    assert before == after                               # nothing touched, incl. updated_at


def test_incremental_new_partition_only_loads_new(conn, tmp_path):
    write_partition(tmp_path, "2026-09-01", rows(0, 10))
    ingest(conn, tmp_path)
    write_partition(tmp_path, "2026-09-02", rows(10, 5))
    _, t = ingest(conn, tmp_path)
    assert (t.files_processed, t.rows_inserted) == (1, 5)
    assert counts(conn) == (15, 2)


def test_revised_file_updates_only_changed_records(conn, tmp_path):
    write_partition(tmp_path, "2026-09-01", rows(0, 10))
    ingest(conn, tmp_path)
    revised = rows(0, 10)
    revised[3] = make_row(3, mileage=777777)             # same keys, one changed record
    write_partition(tmp_path, "2026-09-01", revised)     # same filename, new content hash
    _, t = ingest(conn, tmp_path)
    assert (t.rows_inserted, t.rows_updated, t.rows_unchanged) == (0, 1, 9)
    assert counts(conn) == (10, 2)                       # two file versions checkpointed
    assert conn.execute("select (payload->>'mileage')::int from raw.autotrader_records where primary_key='pk000003'").fetchone()[0] == 777777


def test_stale_observation_does_not_overwrite_newer(conn, tmp_path):
    from datetime import timedelta
    from tests.fixtures.synthetic import BASE_TS
    write_partition(tmp_path / "a", "2026-09-02", [make_row(1, _lastSeenAt=BASE_TS + timedelta(days=5), mileage=5)])
    ingest(conn, tmp_path / "a")
    write_partition(tmp_path / "b", "2026-09-01", [make_row(1, _lastSeenAt=BASE_TS + timedelta(days=1), mileage=1)])
    _, t = ingest(conn, tmp_path / "b")
    assert t.rows_updated == 0 and t.rows_unchanged == 1
    assert conn.execute("select (payload->>'mileage')::int from raw.autotrader_records").fetchone()[0] == 5


def test_invalid_schema_fails_before_any_raw_write(conn, tmp_path):
    write_partition(tmp_path, "2026-09-01", rows(0, 5))
    write_partition(tmp_path, "2026-09-02", rows(5, 5), drop=("kbbFairPriceHigh",))
    with pytest.raises(ContractError, match="kbbFairPriceHigh"):
        ingest(conn, tmp_path)
    assert counts(conn) == (0, 0)                        # even the valid file was not loaded
    run = conn.execute("select status, error_summary from meta.pipeline_runs").fetchone()
    assert run[0] == "failed" and "kbbFairPriceHigh" in run[1]


def test_failed_load_rolls_back_and_is_not_marked_processed(conn, tmp_path):
    from src.ingestion.loader import load_file
    from src.ingestion.source import discover_local
    import pyarrow.parquet as pq
    write_partition(tmp_path, "2026-09-01", rows(0, 5))
    _, files = discover_local(tmp_path)
    bad = pq.read_table(files[0].local_path).to_pylist()
    bad[4]["_lastSeenAt"] = None                         # NOT NULL violation mid-file, bypassing validation
    from tests.fixtures.synthetic import make_table
    with pytest.raises(Exception):
        load_file(conn, files[0], make_table(bad))
    conn.rollback()
    assert counts(conn) == (0, 0)
    _, t = ingest(conn, tmp_path)                        # corrected rerun succeeds
    assert t.rows_inserted == 5 and counts(conn) == (5, 1)
