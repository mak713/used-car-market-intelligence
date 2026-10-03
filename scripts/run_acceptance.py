"""Run the blueprint's end-to-end acceptance scenarios and write docs/acceptance_results.md.

Every number in the report is measured by this script in the same run. Run from the repo root:
    HF_HOME=$PWD/.cache/hf .venv/bin/python scripts/run_acceptance.py
Needs the project Postgres container; scenarios 1-3 drop/recreate the main project database.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.db.config import connect  # noqa: E402

REVISION = "1e325fd8d9d05895fc2d26a2eac5a36f3ef07487"
MAIN_DB = os.environ.get("POSTGRES_DB", "used_car_intelligence")
SCRATCH_DB = "uc_acceptance_scratch"
PY = str(REPO / ".venv" / "bin" / "python")
BROKEN_MODEL = REPO / "dbt" / "models" / "marts" / "zz_acceptance_broken.sql"

results: list[dict] = []


def recreate_db(name: str) -> None:
    with connect("postgres", autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{name}"')


def scalar(db: str, sql: str):
    with connect(db) as c:
        return c.execute(sql).fetchone()[0]


def snapshot(db: str) -> dict:
    q = lambda s: scalar(db, s)
    return {
        "raw": q("select count(*) from raw.autotrader_records"),
        "processed_files": q("select count(*) from meta.processed_files"),
        "pipeline_runs": q("select count(*) from meta.pipeline_runs"),
        "stg": q("select count(*) from staging.stg_autotrader_listings"),
        "fct": q("select count(*) from warehouse.fct_listings"),
        "dim_vehicle": q("select count(*) from warehouse.dim_vehicle"),
        "dim_seller": q("select count(*) from warehouse.dim_seller"),
        "dim_geography": q("select count(*) from warehouse.dim_geography"),
        "dim_date": q("select count(*) from warehouse.dim_date"),
        "fct_fingerprint": q("""select md5(string_agg(concat_ws('|', listing_id, vehicle_key, seller_key,
            geography_key, first_seen_date_key, mileage, kbb_fair_price_low, kbb_fair_price_high),
            ',' order by listing_id)) from warehouse.fct_listings"""),
        "raw_fingerprint": q("select md5(string_agg(primary_key || record_hash, ',' order by primary_key)) from raw.autotrader_records"),
    }


def flow(db: str, *args: str) -> dict:
    env = {**os.environ, "POSTGRES_DB": db, "HF_HOME": str(REPO / ".cache" / "hf")}
    t = time.perf_counter()
    p = subprocess.run([PY, "-m", "src.orchestration.flow", *args], cwd=REPO, env=env,
                       text=True, capture_output=True)
    out = p.stdout + p.stderr
    dbt = re.findall(r"Done\. PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+)", out)
    return {"rc": p.returncode, "secs": round(time.perf_counter() - t, 1), "out": out,
            "dbt": tuple(map(int, dbt[-1])) if dbt else None}


def last_run(db: str) -> dict:
    with connect(db) as c:
        cols = ["status", "files_discovered", "files_processed", "rows_read", "rows_inserted",
                "rows_updated", "rows_unchanged", "dbt_status", "smoke_status", "error_summary"]
        row = c.execute(f"select {','.join(cols)} from meta.pipeline_runs order by started_at desc limit 1").fetchone()
    return dict(zip(cols, row))


class Scenario:
    def __init__(self, name: str):
        self.name, self.checks, self.notes = name, [], []

    def check(self, desc: str, ok: bool, evidence: str = "") -> bool:
        self.checks.append((desc, bool(ok), evidence))
        print(("  PASS " if ok else "  FAIL ") + desc + (f"  [{evidence}]" if evidence else ""))
        return ok

    def done(self) -> None:
        results.append({"name": self.name, "checks": self.checks, "notes": self.notes,
                        "ok": all(c[1] for c in self.checks)})


def synthetic_dir(path: Path, *, bad: bool) -> None:
    from tests.fixtures.synthetic import make_row, write_partition
    shutil.rmtree(path, ignore_errors=True)
    write_partition(path, "2026-09-01", [make_row(i) for i in range(20)])
    write_partition(path, "2026-09-02", [make_row(i) for i in range(20, 40)],
                    drop=("kbbFairPriceHigh",) if bad else ())


def main() -> int:
    started = datetime.now(timezone.utc)
    from src.ingestion.source import discover_hub
    head_rev, _ = discover_hub()
    meta = {"pinned_revision": REVISION, "hub_head_at_run": head_rev}
    print("pinned", REVISION, "hub head", head_rev)

    # 1. Clean bootstrap (real source, main DB) ------------------------------------------------
    print("== 1 clean bootstrap + real source ingestion")
    s = Scenario("1. Clean bootstrap (fresh DB, real source, full pipeline)")
    recreate_db(MAIN_DB)
    r = flow(MAIN_DB, "--revision", REVISION)
    run, snap1 = last_run(MAIN_DB), snapshot(MAIN_DB)
    s.check("flow exit code 0", r["rc"] == 0, f"rc={r['rc']}, {r['secs']}s")
    s.check("30 partitions discovered and processed", run["files_discovered"] == 30 == run["files_processed"], str(run))
    s.check("raw rows == rows read == inserted", snap1["raw"] == run["rows_read"] == run["rows_inserted"] > 0, f"raw={snap1['raw']}")
    s.check("dbt build green", r["dbt"] is not None and r["dbt"][2] == 0 and r["dbt"][3] == 0, f"PASS/WARN/ERROR/SKIP={r['dbt']}")
    s.check("run recorded success incl. dbt+smoke", (run["status"], run["dbt_status"], run["smoke_status"]) == ("success",) * 3)
    s.check("warehouse populated", snap1["fct"] > 0 and snap1["dim_vehicle"] > 0, f"fct={snap1['fct']}")
    s.notes.append(f"Snapshot: {snap1}")
    s.done()

    # 2. Idempotent rerun ------------------------------------------------------------------------
    print("== 2 idempotent rerun")
    s = Scenario("2. Idempotent rerun (no source change)")
    r = flow(MAIN_DB, "--revision", REVISION)
    run, snap2 = last_run(MAIN_DB), snapshot(MAIN_DB)
    s.check("flow exit code 0", r["rc"] == 0, f"{r['secs']}s")
    s.check("zero files processed / zero rows read", run["files_processed"] == 0 == run["rows_read"], str(run))
    same = {k: (snap1[k], snap2[k]) for k in snap1 if k != "pipeline_runs" and snap1[k] != snap2[k]}
    s.check("all table counts and key fingerprints unchanged", not same, f"diff={same}")
    s.check("only pipeline_runs grew (by 1)", snap2["pipeline_runs"] == snap1["pipeline_runs"] + 1)
    s.check("dbt tests green", r["dbt"] is not None and r["dbt"][2] == 0, f"{r['dbt']}")
    s.done()

    # 3. Incremental (real partitions, windowed by date) ---------------------------------------
    print("== 3 incremental run")
    s = Scenario("3. Incremental run (real partitions: first 21 days, then the remaining 9)")
    recreate_db(MAIN_DB)
    flow(MAIN_DB, "--revision", REVISION, "--date-to", "2026-09-10")
    a_run, a = last_run(MAIN_DB), snapshot(MAIN_DB)
    r = flow(MAIN_DB, "--revision", REVISION)
    b_run, b = last_run(MAIN_DB), snapshot(MAIN_DB)
    import pyarrow.parquet as pq
    new_files = sorted((REPO / "data/raw/car-listings/data").glob("2026-09-1[1-9].parquet"))
    new_rows = sum(pq.ParquetFile(f).metadata.num_rows for f in new_files)
    new_fact = sum(sum(1 for t in pq.read_table(f, columns=["listingType"]).column(0).to_pylist() if t != "New") for f in new_files)
    s.check("first run processed 21 files", a_run["files_processed"] == 21, f"rows={a_run['rows_inserted']}, fct={a['fct']}")
    s.check("second run processed only the 9 new files", b_run["files_processed"] == 9 and b_run["rows_read"] == new_rows, f"processed={b_run['files_processed']}, rows={b_run['rows_read']} (expected {new_rows})")
    s.check("raw grew by exactly the new rows", b["raw"] - a["raw"] == new_rows, f"{a['raw']} -> {b['raw']}")
    s.check("fact grew by exactly the new used/certified rows", b["fct"] - a["fct"] == new_fact, f"{a['fct']} -> {b['fct']} (expected +{new_fact})")
    s.check("end state equals clean-bootstrap state", b["raw_fingerprint"] == snap1["raw_fingerprint"] and b["fct_fingerprint"] == snap1["fct_fingerprint"])
    s.check("dbt green after incremental run", r["dbt"] is not None and r["dbt"][2] == 0, f"{r['dbt']}")
    s.notes.append("Incremental behaviour is shown on real partitions by date-windowing discovery; the public source did not publish new partitions during the run.")
    s.done()

    # 4. Invalid schema (synthetic, scratch DB) -------------------------------------------------
    print("== 4 invalid schema")
    s = Scenario("4. Invalid-schema file (synthetic; scratch DB)")
    recreate_db(SCRATCH_DB)
    tmp = Path(tempfile.mkdtemp(prefix="uc_accept_"))
    synthetic_dir(tmp, bad=True)
    r = flow(SCRATCH_DB, "--source-dir", str(tmp))
    run = last_run(SCRATCH_DB)
    s.check("flow fails (non-zero exit)", r["rc"] != 0, f"rc={r['rc']}")
    s.check("error names the missing column", "kbbFairPriceHigh" in (run["error_summary"] or ""), (run["error_summary"] or "")[:160])
    s.check("no raw rows written (even from the valid file)", scalar(SCRATCH_DB, "select count(*) from raw.autotrader_records") == 0)
    s.check("no file marked processed", scalar(SCRATCH_DB, "select count(*) from meta.processed_files") == 0)
    s.check("run recorded as failed, dbt not run", run["status"] == "failed" and run["dbt_status"] is None, str(run["status"]))
    synthetic_dir(tmp, bad=False)  # corrected file, same name
    r = flow(SCRATCH_DB, "--source-dir", str(tmp))
    s.check("corrected rerun succeeds and loads both files", r["rc"] == 0 and scalar(SCRATCH_DB, "select count(*) from meta.processed_files") == 2,
            f"raw={scalar(SCRATCH_DB, 'select count(*) from raw.autotrader_records')}")
    s.done()

    # 5. Controlled dbt failure (scratch DB) ---------------------------------------------------
    print("== 5 controlled dbt failure")
    s = Scenario("5. Controlled dbt failure and corrected rerun (scratch DB)")
    BROKEN_MODEL.write_text("select nonexistent_column from {{ ref('fct_listings') }}\n")
    try:
        r = flow(SCRATCH_DB, "--source-dir", str(tmp))
        run = last_run(SCRATCH_DB)
        s.check("flow fails visibly", r["rc"] != 0, f"rc={r['rc']}")
        s.check("run recorded failed with dbt_status=failed", run["status"] == "failed" and run["dbt_status"] == "failed", f"{run['status']}/{run['dbt_status']}")
        s.check("error summary mentions dbt", "dbt build failed" in (run["error_summary"] or ""), (run["error_summary"] or "")[:160])
        s.check("smoke checks not run after dbt failure", run["smoke_status"] is None)
    finally:
        BROKEN_MODEL.unlink(missing_ok=True)
    r = flow(SCRATCH_DB, "--source-dir", str(tmp))
    run = last_run(SCRATCH_DB)
    s.check("corrected rerun succeeds", r["rc"] == 0 and run["status"] == "success" and run["dbt_status"] == "success", f"{run['status']}/{run['dbt_status']}/{run['smoke_status']}")
    s.done()
    shutil.rmtree(tmp, ignore_errors=True)
    with connect("postgres", autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')

    # 6. Download retry (in-process, patched) --------------------------------------------------
    print("== 6 download retry")
    s = Scenario("6. Download task retries on transient failure, then succeeds")
    recreate_db(SCRATCH_DB)
    tmp = Path(tempfile.mkdtemp(prefix="uc_accept_"))
    synthetic_dir(tmp, bad=False)
    code = (
        "import sys; sys.path.insert(0, '.')\n"
        "from src.ingestion import pipeline\n"
        "calls = {'n': 0}; orig = pipeline.download\n"
        "def flaky(*a, **k):\n"
        "    calls['n'] += 1\n"
        "    if calls['n'] <= 2: raise ConnectionError('simulated network failure')\n"
        "    return orig(*a, **k)\n"
        "pipeline.download = flaky\n"
        "from src.orchestration.flow import used_car_market_pipeline\n"
        f"st = used_car_market_pipeline({str(tmp)!r}, return_state=True)\n"
        "print('DOWNLOAD_CALLS', calls['n'], 'COMPLETED', st.is_completed())\n")
    p = subprocess.run([PY, "-c", code], cwd=REPO, env={**os.environ, "POSTGRES_DB": SCRATCH_DB}, text=True, capture_output=True)
    m = re.search(r"DOWNLOAD_CALLS (\d+) COMPLETED (\w+)", p.stdout + p.stderr)
    s.check("download attempted 3 times (2 retries) then flow completed", bool(m) and m.group(1) == "3" and m.group(2) == "True", m.group(0) if m else (p.stdout + p.stderr)[-300:])
    s.done()
    shutil.rmtree(tmp, ignore_errors=True)
    with connect("postgres", autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')

    # 7. pytest suite (unit + integration incl. changed-record upsert & dedupe fixtures) -------
    print("== 7 pytest")
    s = Scenario("7. Python test suite (synthetic fixtures; includes upsert + dedupe + idempotency)")
    p = subprocess.run([PY, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=REPO, text=True, capture_output=True)
    summary = (p.stdout.strip().splitlines() or [""])[-1]
    s.check("pytest passes", p.returncode == 0, summary)
    s.done()

    # Final: main DB left in the full, built state ---------------------------------------------
    final = snapshot(MAIN_DB)
    write_report(started, meta, final)
    ok = all(x["ok"] for x in results)
    print("\nACCEPTANCE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def write_report(started, meta, final) -> None:
    lines = ["# Acceptance results", "",
             f"Run started {started:%Y-%m-%d %H:%M} UTC by `scripts/run_acceptance.py`. All values below were measured in that run.", "",
             f"- Source: `rebrowser/autotrader-dataset`, pinned revision `{meta['pinned_revision']}` (Hub head at run time: `{meta['hub_head_at_run']}`).",
             "- Real-source behaviour (scenarios 1–3) is kept separate from synthetic-fixture behaviour (scenarios 4–7); the live source has no cross-file overlap, so upsert and dedupe are demonstrated on fixtures only.",
             "- **Not covered here:** Power BI refresh (requires Power BI Desktop; human verification).", "",
             "| Scenario | Result |", "|---|---|"]
    for r in results:
        lines.append(f"| {r['name']} | {'PASS' if r['ok'] else '**FAIL**'} |")
    for r in results:
        lines += ["", f"## {r['name']}", ""]
        lines += [f"- {'PASS' if ok else '**FAIL**'} — {d}" + (f" — `{e}`" if e else "") for d, ok, e in r["checks"]]
        lines += [f"- Note: {n}" for n in r["notes"]]
    lines += ["", "## Final state of the project database", "", "```", *[f"{k}: {v}" for k, v in final.items()], "```", ""]
    (REPO / "docs" / "acceptance_results.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
