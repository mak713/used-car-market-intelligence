# Acceptance results

Run started 2026-10-03 23:46 UTC by `scripts/run_acceptance.py`. All values below were measured in that run.

- Source: `rebrowser/autotrader-dataset`, pinned revision `1e325fd8d9d05895fc2d26a2eac5a36f3ef07487` (Hub head at run time: `1e325fd8d9d05895fc2d26a2eac5a36f3ef07487`).
- Real-source behaviour (scenarios 1–3) is kept separate from synthetic-fixture behaviour (scenarios 4–7); the live source has no cross-file overlap, so upsert and dedupe are demonstrated on fixtures only.
- **Point-in-time record** for revision `1e325fd8…`; later counts are in `docs/implementation_status.md`.
- **Not covered here:** Power BI refresh — verified separately by the user (see `docs/implementation_status.md`).

| Scenario | Result |
|---|---|
| 1. Clean bootstrap (fresh DB, real source, full pipeline) | PASS |
| 2. Idempotent rerun (no source change) | PASS |
| 3. Incremental run (real partitions: first 21 days, then the remaining 9) | PASS |
| 4. Invalid-schema file (synthetic; scratch DB) | PASS |
| 5. Controlled dbt failure and corrected rerun (scratch DB) | PASS |
| 6. Download task retries on transient failure, then succeeds | PASS |
| 7. Python test suite (synthetic fixtures; includes upsert + dedupe + idempotency) | PASS |

## 1. Clean bootstrap (fresh DB, real source, full pipeline)

- PASS — flow exit code 0 — `rc=0, 35.1s`
- PASS — 30 partitions discovered and processed — `{'status': 'success', 'files_discovered': 30, 'files_processed': 30, 'rows_read': 24608, 'rows_inserted': 24608, 'rows_updated': 0, 'rows_unchanged': 0, 'dbt_status': 'success', 'smoke_status': 'success', 'error_summary': None}`
- PASS — raw rows == rows read == inserted — `raw=24608`
- PASS — dbt build green — `PASS/WARN/ERROR/SKIP=(54, 0, 0, 0)`
- PASS — run recorded success incl. dbt+smoke
- PASS — warehouse populated — `fct=22098`
- Note: Snapshot: {'raw': 24608, 'processed_files': 30, 'pipeline_runs': 1, 'stg': 24608, 'fct': 22098, 'dim_vehicle': 11013, 'dim_seller': 8191, 'dim_geography': 4179, 'dim_date': 42, 'fct_fingerprint': '13b1c7749e72de9fed2a254752f3a5ae', 'raw_fingerprint': 'db2a8a1bf30fdae1ed1d35934bab0160'}

## 2. Idempotent rerun (no source change)

- PASS — flow exit code 0 — `22.8s`
- PASS — zero files processed / zero rows read — `{'status': 'success', 'files_discovered': 30, 'files_processed': 0, 'rows_read': 0, 'rows_inserted': 0, 'rows_updated': 0, 'rows_unchanged': 0, 'dbt_status': 'success', 'smoke_status': 'success', 'error_summary': None}`
- PASS — all table counts and key fingerprints unchanged — `diff={}`
- PASS — only pipeline_runs grew (by 1)
- PASS — dbt tests green — `(54, 0, 0, 0)`

## 3. Incremental run (real partitions: first 21 days, then the remaining 9)

- PASS — first run processed 21 files — `rows=16591, fct=15110`
- PASS — second run processed only the 9 new files — `processed=9, rows=8017 (expected 8017)`
- PASS — raw grew by exactly the new rows — `16591 -> 24608`
- PASS — fact grew by exactly the new used/certified rows — `15110 -> 22098 (expected +6988)`
- PASS — end state equals clean-bootstrap state
- PASS — dbt green after incremental run — `(54, 0, 0, 0)`
- Note: Incremental behaviour is shown on real partitions by date-windowing discovery; the public source did not publish new partitions during the run.

## 4. Invalid-schema file (synthetic; scratch DB)

- PASS — flow fails (non-zero exit) — `rc=1`
- PASS — error names the missing column — `ContractError: 2026-09-02.parquet: missing required column: kbbFairPriceHigh`
- PASS — no raw rows written (even from the valid file)
- PASS — no file marked processed
- PASS — run recorded as failed, dbt not run — `failed`
- PASS — corrected rerun succeeds and loads both files — `raw=40`

## 5. Controlled dbt failure and corrected rerun (scratch DB)

- PASS — flow fails visibly — `rc=1`
- PASS — run recorded failed with dbt_status=failed — `failed/failed`
- PASS — error summary mentions dbt — `RuntimeError: dbt build failed: [0m23:48:51  55 of 55 ERROR creating sql table model warehouse.zz_acceptance_broken ......... [[31mERROR[0m in 0.04s] | [0m2`
- PASS — smoke checks not run after dbt failure
- PASS — corrected rerun succeeds — `success/success/success`

## 6. Download task retries on transient failure, then succeeds

- PASS — download attempted 3 times (2 retries) then flow completed — `DOWNLOAD_CALLS 3 COMPLETED True`

## 7. Python test suite (synthetic fixtures; includes upsert + dedupe + idempotency)

- PASS — pytest passes — `40 passed in 14.66s`

## Final state of the project database

```
raw: 24608
processed_files: 30
pipeline_runs: 2
stg: 24608
fct: 22098
dim_vehicle: 11013
dim_seller: 8191
dim_geography: 4179
dim_date: 42
fct_fingerprint: 13b1c7749e72de9fed2a254752f3a5ae
raw_fingerprint: db2a8a1bf30fdae1ed1d35934bab0160
```
