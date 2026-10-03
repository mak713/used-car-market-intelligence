"""Prefect flow `used_car_market_pipeline`:
discover -> download changed -> validate -> load raw -> dbt build -> smoke checks -> record summary.

Retries: only the download task (network). Contract failures, load errors, dbt failures and failed
smoke checks fail visibly with no retry. Run state lives in meta.pipeline_runs.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Keep Prefect's local state inside the repo (gitignored) and avoid network calls.
os.environ.setdefault("PREFECT_HOME", str(Path(__file__).resolve().parents[2] / ".prefect"))
os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")

from prefect import flow, get_run_logger, task  # noqa: E402

from src.db.bootstrap import apply_ddl  # noqa: E402
from src.db.config import connect  # noqa: E402
from src.ingestion import pipeline, runs  # noqa: E402
from src.orchestration.dbt_runner import run_dbt  # noqa: E402


@task(name="discover_source_files")
def discover_source_files(source_dir, revision, date_from, date_to):
    with connect() as conn:
        apply_ddl(conn)
        resolved_rev, files = pipeline.discover(source_dir, revision, date_from, date_to)
        run_id = runs.start_run(conn, resolved_rev)
        runs.update_run(conn, run_id, files_discovered=len(files))
        get_run_logger().info("run %s: %d partitions at revision %s", run_id, len(files), resolved_rev)
    return run_id, files


@task(name="download_changed_files", retries=2, retry_delay_seconds=5)
def download_changed_files(files, source_dir):
    with connect() as conn:
        todo = runs.select_unprocessed(files, runs.processed_keys(conn))
        pipeline.download(todo, source_dir)
        todo = runs.select_unprocessed(todo, runs.processed_keys(conn))  # hashes now known
    get_run_logger().info("%d new/changed files to process", len(todo))
    return todo


@task(name="validate_source_files")
def validate_source_files(todo):
    return pipeline.validate(todo)  # raises ContractError; nothing has been written yet


@task(name="load_raw_records")
def load_raw_records(todo, run_id):
    totals = pipeline.IngestTotals()
    with connect() as conn:
        try:
            pipeline.load(conn, todo, run_id, totals)
        finally:  # keep counters for files committed before a failure
            runs.update_run(conn, run_id, files_processed=totals.files_processed,
                            rows_read=totals.rows_read, rows_inserted=totals.rows_inserted,
                            rows_updated=totals.rows_updated, rows_unchanged=totals.rows_unchanged)
    return totals


@task(name="run_dbt_build")
def run_dbt_build(run_id):
    r = run_dbt("build", capture=True)
    log = get_run_logger()
    log.info("dbt build exit code %s\n%s", r.returncode, "\n".join(r.stdout.splitlines()[-12:]))
    with connect() as conn:
        runs.update_run(conn, run_id, dbt_status="success" if r.returncode == 0 else "failed")
    if r.returncode != 0:
        fails = [l for l in r.stdout.splitlines() if "FAIL" in l or "ERROR" in l]
        raise RuntimeError("dbt build failed: " + " | ".join(fails[:5]))


@task(name="run_pipeline_smoke_checks")
def run_pipeline_smoke_checks(run_id):
    checks = {
        "raw rows == distinct primary keys":
            "select count(*) = count(distinct primary_key) and count(*) > 0 from raw.autotrader_records",
        "fct_listings non-empty and unique listing_id":
            "select count(*) > 0 and count(*) = count(distinct listing_id) from warehouse.fct_listings",
        "fact == latest deduplicated listings with an in-scope listing type":
            """select (select count(*) from warehouse.fct_listings) =
                      (select count(*) from intermediate.int_listings_deduped
                        where listing_type in ('Used','Certified','Third-Party Certified'))""",
        "no orphan fact keys":
            """select count(*) = 0 from warehouse.fct_listings f
               left join warehouse.dim_vehicle v using (vehicle_key)
               left join warehouse.dim_seller s using (seller_key)
               left join warehouse.dim_geography g using (geography_key)
               where v.vehicle_key is null or s.seller_key is null or g.geography_key is null""",
        "no processed file recorded twice for one content hash":
            "select count(*) = 0 from (select content_hash from meta.processed_files group by 1 having count(*) > 1) x",
        "no listing/asking-price column in warehouse (reference values only)":
            """select count(*) = 0 from information_schema.columns
               where table_schema = 'warehouse' and column_name ~* '(price|asking|sale)'
                 and column_name not in ('kbb_fair_price_low','kbb_fair_price_high','is_reduced_price',
                                         'is_no_haggle_price')""",
    }
    failed = []
    with connect() as conn:
        for name, sql in checks.items():
            if not conn.execute(sql).fetchone()[0]:
                failed.append(name)
        runs.update_run(conn, run_id, smoke_status="failed" if failed else "success")
    if failed:
        raise RuntimeError("smoke checks failed: " + "; ".join(failed))
    return len(checks)


@task(name="record_run_summary")
def record_run_summary(run_id):
    with connect() as conn:
        runs.finish_run(conn, run_id, "success")
        row = conn.execute("""select files_discovered, files_processed, rows_read, rows_inserted,
                                     rows_updated, rows_unchanged from meta.pipeline_runs
                              where run_id = %s""", (run_id,)).fetchone()
    get_run_logger().info("run %s success: discovered=%s processed=%s read=%s inserted=%s updated=%s unchanged=%s",
                          run_id, *row)
    return row


@flow(name="used_car_market_pipeline")
def used_car_market_pipeline(source_dir: str | None = None, revision: str | None = None,
                             date_from: date | None = None, date_to: date | None = None):
    sd = Path(source_dir) if source_dir else None
    run_id, files = discover_source_files(sd, revision, date_from, date_to)
    try:
        todo = download_changed_files(files, sd)
        validate_source_files(todo)
        load_raw_records(todo, run_id)
        run_dbt_build(run_id)
        run_pipeline_smoke_checks(run_id)
        record_run_summary(run_id)
    except Exception as e:
        with connect() as conn:
            runs.finish_run(conn, run_id, "failed", f"{type(e).__name__}: {e}"[:2000])
        raise
    return str(run_id)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the end-to-end pipeline")
    ap.add_argument("--source-dir")
    ap.add_argument("--revision")
    ap.add_argument("--date-from", type=date.fromisoformat)
    ap.add_argument("--date-to", type=date.fromisoformat)
    a = ap.parse_args()
    state = used_car_market_pipeline(a.source_dir, a.revision, a.date_from, a.date_to, return_state=True)
    sys.exit(0 if state.is_completed() else 1)


if __name__ == "__main__":
    main()
