# Implementation status

_Last updated: 2026-10-08. Authoritative spec: `docs/…Blueprint.docx`; project rules are kept in a local, gitignored agent file (not part of the published repo)._

## Current phase
**All phases (0–7) complete; all V1 acceptance criteria are met.** Power BI report built, refreshed and visually reviewed; `.pbix` and three screenshots committed. Sections below dated "as of Phase N" or describing the acceptance run are historical evidence for revision `1e325fd8…` (30 partitions, 24,608 raw / 22,098 fact); the latest state is in the next section.

## Final state and Power BI refresh (2026-10-08)
- Source later published 5 new partitions (2026-09-20..2026-09-24, revision `f9511a90cd443f814be64874baead99d9d20a850`). A normal pipeline run (`meta.pipeline_runs`: success, dbt success, smoke success) processed only those 5 files — 2,237 rows inserted, 0 updated — and the 30 older files were not reprocessed. Local history now spans 35 partitions (2026-08-21..2026-09-24).
- Warehouse (queried after the refresh): raw 26,845; `fct_listings` 23,950 (Used 20,466, Certified 3,136, Third-Party Certified 348; 2,895 New excluded); market-value eligible 21,611; dim_vehicle 11,590; dim_seller 8,607; dim_geography 4,318; dim_date 48 (2026-08-21..2026-10-07); max `source_observation_count` still 1.
- Power BI refresh succeeded against the warehouse (`powerbi/Used_Car_Market_Intelligence.pbix`); screenshots in `docs/images/`. Final dashboard values: Listing Count 23,950; Market-Value Eligible 21,611; Median Reference Value $27,043; Median Mileage 43,819.5; Median Days on Market 12; Reduced Price Rate 22.58%; Hot Listing Rate 2.79%; Certified Inventory Share 14.55%; Median Reference-Value Spread $2,600.
- The full acceptance suite was not re-run after the refresh; `docs/acceptance_results.md` remains the point-in-time run on the original revision.

## Completed
- Branch renamed `master` → `main` (baseline commit preserved; `.git/config.lock` is a sandbox
  /dev/null overlay so git could not rewrite config, harmless — no remotes/upstreams exist).
- Toolchain: uv 0.12.23 in `.tools/` (fetched from the PyPI wheel), Python 3.12.15, `.venv/` via
  `uv sync` (a project-local uv under gitignored `.tools/` was used during development only).
  dbt-core 1.12.5, prefect 3.8.7, pyarrow 25.0.1, pandas 3.0.6, psycopg 3.3.6.
- Docker Postgres 16 (`docker compose up -d`, container `used_car_postgres`, 127.0.0.1:5432), healthy.
- Source preflight (live, revision `1e325fd8d9d05895fc2d26a2eac5a36f3ef07487`): 30 Parquet partitions
  2026-08-21..2026-09-19, **24,608 rows**, one schema (71 cols, typed — `year` uint16, `sellerId` uint64
  nullable, `kbbFairPriceLow/High` double, `salePrice`/`vin`/`kbbFairPurchasePrice`/`sellerRating`
  strings all `[PREMIUM]`). `_primaryKey == listingId`, all distinct: **zero cross-file overlap**.
  Partition date == `_firstSeenAt` date for every row; `_lastSeenAt` runs to 2026-10-01 (files get revised).
  Types: Used 18,855 / Certified 2,918 / Third-Party Certified 325 / New 2,510 (New excluded from fact).
  Quirks: kbb low/high null 1,764 rows; low==0 in 1,316 rows (invalid → ineligible); kbbVehicleId null
  1,212 and 0 in 897 (treat 0 as absent); **13** rows with null sellerId (needs an Unknown seller member; an earlier note of 8,460 was a misread — that is the distinct-seller count);
  years 1987..2027; low>high 0; negative mileage/DOM 0. Card license: **CC BY-NC 4.0** (attribute; non-commercial).
- Code written (Phase 1): `src/db/{config,bootstrap,ddl/*}`, `src/ingestion/{contract,normalize,source,runs,loader,pipeline,cli}.py`,
  synthetic fixtures `tests/fixtures/synthetic.py`.
- Integration tests (`tests/integration/*`) are executed against the project Postgres; see results below.

## Decisions / deviations
- Listing scope: fact includes Used, Certified, Third-Party Certified (types kept distinct); excludes New. (user-approved)
- Upsert refinement: update only if `record_hash` differs **and** incoming `last_seen_at >= stored`
  (a stale partition revision never overwrites a newer observation). Same-hash rows are no-ops.
- `meta.processed_files` holds successful file versions only (PK source_file+content_hash); failures are
  recorded in `meta.pipeline_runs.error_summary`, so failed files stay eligible for rerun.
- Contract validates all downloaded files before any raw write; extra columns OK.
- Source identity: Hub LFS sha256, re-verified after download; repo revision stored per file; `--revision` pins it.

## Verified results (as of Phase 2)
- DB access: sandbox cannot reach Postgres, so DB-touching project commands (ingestion CLI, pytest integration, dbt, Prefect) run with the sandbox disabled per user authorization (Option B, narrow). Everything else stays sandboxed.
- `pytest tests` -> 28 passed (21 unit, 6 ingestion integration, 1 dbt-on-fixtures integration).
- Real ingestion at revision 1e325fd8…: run 1 = 30 files, 24,608 read/inserted; run 2 (no change) = 0 files processed. raw.autotrader_records = 24,608 rows (24,608 distinct primary_key/listing_id); meta.processed_files = 30 rows (sum row_count 24,608).
- `python -m src.orchestration.dbt_runner build` -> PASS=54 (1 seed, 7 tables, 1 view, 45 tests), 0 errors.
- Warehouse counts: stg/deduped/enriched 24,608; fct_listings 22,098 (Used 18,855, Third-Party Certified 325, Certified 2,918; New 2,510 excluded); market-value-eligible 19,869; dim_vehicle 11,013; dim_seller 8,191 (incl. 1 Unknown, 13 facts); dim_geography 4,179; dim_date 42 (2026-08-21..2026-10-01); state_regions seed 51.
- Fact rows with kbb low = 0: 610 (ineligible); null range: 1,619. source_observation_count max = 1 on real data (no overlap). Dedupe and changed-record upsert are demonstrated only with synthetic fixtures (tests/integration).

## Phase 2 decisions / deviations
- `dim_vehicle` key = deterministic md5 over year/make/model/trim/body/engine/drivetrain/transmission/fuel, NOT kbb_vehicle_id: measured 1,414 of 9,268 kbbVehicleIds map to >1 full configuration (and 1 to >1 year/make/model). kbb_vehicle_id is kept as latest-observed attribute. (Blueprint says prefer kbb id "when stable".)
- reference_value_midpoint/spread/spread_pct are NULL unless eligible (low>0, high>=low, both non-null).
- kbb_vehicle_id 0 -> NULL. vehicle_age_years = max(year(last_seen_at) - model year, 0).
- dim_geography keeps ZIP/city/state grain (176 ZIPs carry >1 city name in the real data; genuine, e.g. Boston/Allston).

## Phase 3–5 results
- Phase 3: eight `sql/0N_*.sql` analyses all execute and return rows (`tests/integration/test_sql_analyses.py`); notes in `docs/sql_analysis.md`; EXPLAIN (ANALYZE, BUFFERS) of query 05 documented in `docs/explain/` (6,019 ms nested loop -> 67.5 ms after restructuring; cause = multi-column join mis-estimate, not stale stats).
- Phase 4: Prefect flow `used_car_market_pipeline` (`src/orchestration/flow.py`, run: `HF_HOME=$PWD/.cache/hf .venv/bin/python -m src.orchestration.flow [--revision SHA] [--source-dir D] [--date-from/--date-to]`). Only the download task retries (2x, 5 s). Run state in `meta.pipeline_runs` (counters, dbt_status, smoke_status, error_summary). Prefect runs an ephemeral local server with state in gitignored `.prefect/`.
- Phase 5: `scripts/run_acceptance.py` -> `docs/acceptance_results.md`: ACCEPTANCE PASS (clean bootstrap, idempotent rerun, real-partition incremental 21+9 files, invalid schema + corrected rerun, controlled dbt failure + corrected rerun, download retry 3 calls, pytest 40 passed). Pinned source revision 1e325fd8…; Hub head equalled it at run time.
- Main DB was left in the full built state (24,608 raw; 22,098 fact) at acceptance time; superseded by the refreshed state above.

## Post-audit corrections (final)
- dbt reconciliation test and Prefect smoke check now compare `fct_listings` to `int_listings_deduped` filtered to the fact listing types (latest observation decides scope), not to any-historical in-scope raw observation.
- New synthetic transition test (`test_fact_inclusion_follows_latest_observation_listing_type`): Used->New listing absent, New->Used present. Live data still has zero cross-file overlap.
- Public setup uses `uv sync`; local agent files (`CLAUDE.md`, `.claude/`) are gitignored.
- Re-verified: `pytest tests` 40 passed; `dbt build` PASS=54; acceptance re-run ACCEPTANCE PASS; all eight SQL analyses execute (`test_sql_analyses.py`).

## Power BI (Phase 6) — complete
Report built by the user in Power BI Desktop, refreshed after the new partitions loaded, and visually reviewed. The engineering agent did not open or parse the `.pbix`.

## Blockers
None.

## Next
None for V1. Repository ready to push.
