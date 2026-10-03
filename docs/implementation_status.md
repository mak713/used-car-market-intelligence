# Implementation status

_Last updated: 2026-10-03. Authoritative spec: `docs/…Blueprint.docx`; project rules: `CLAUDE.md`._

## Current phase
Phase 1 (Foundation) — **BLOCKED on DB access from the sandbox** (see Blockers). Phase 0 complete.

## Completed
- Branch renamed `master` → `main` (baseline commit preserved; `.git/config.lock` is a sandbox
  /dev/null overlay so git could not rewrite config, harmless — no remotes/upstreams exist).
- Toolchain: uv 0.12.23 in `.tools/` (fetched from the PyPI wheel), Python 3.12.15, `.venv/` via
  `UV_CACHE_DIR=$PWD/.cache/uv UV_PYTHON_INSTALL_DIR=$PWD/.tools/python .tools/uv sync`.
  dbt-core 1.12.5, prefect 3.8.7, pyarrow 25.0.1, pandas 3.0.6, psycopg 3.3.6.
- Docker Postgres 16 (`docker compose up -d`, container `used_car_postgres`, 127.0.0.1:5432), healthy.
- Source preflight (live, revision `1e325fd8d9d05895fc2d26a2eac5a36f3ef07487`): 30 Parquet partitions
  2026-08-21..2026-09-19, **24,608 rows**, one schema (71 cols, typed — `year` uint16, `sellerId` uint64
  nullable, `kbbFairPriceLow/High` double, `salePrice`/`vin`/`kbbFairPurchasePrice`/`sellerRating`
  strings all `[PREMIUM]`). `_primaryKey == listingId`, all distinct: **zero cross-file overlap**.
  Partition date == `_firstSeenAt` date for every row; `_lastSeenAt` runs to 2026-10-01 (files get revised).
  Types: Used 18,855 / Certified 2,918 / Third-Party Certified 325 / New 2,510 (New excluded from fact).
  Quirks: kbb low/high null 1,764 rows; low==0 in 1,316 rows (invalid → ineligible); kbbVehicleId null
  1,212 and 0 in 897 (treat 0 as absent); sellerId null in 8,460 (needs an Unknown seller member);
  years 1987..2027; low>high 0; negative mileage/DOM 0. Card license: **CC BY-NC 4.0** (attribute; non-commercial).
- Code written (Phase 1): `src/db/{config,bootstrap,ddl/*}`, `src/ingestion/{contract,normalize,source,runs,loader,pipeline,cli}.py`,
  synthetic fixtures `tests/fixtures/synthetic.py`.
- **Verified:** `.venv/bin/python -m pytest tests/unit -q` → 21 passed.
- **Written but NOT yet run:** `tests/integration/*` (need DB).

## Decisions / deviations
- Listing scope: fact includes Used, Certified, Third-Party Certified (types kept distinct); excludes New. (user-approved)
- Upsert refinement: update only if `record_hash` differs **and** incoming `last_seen_at >= stored`
  (a stale partition revision never overwrites a newer observation). Same-hash rows are no-ops.
- `meta.processed_files` holds successful file versions only (PK source_file+content_hash); failures are
  recorded in `meta.pipeline_runs.error_summary`, so failed files stay eligible for rerun.
- Contract validates all downloaded files before any raw write; extra columns OK.
- Source identity: Hub LFS sha256, re-verified after download; repo revision stored per file; `--revision` pins it.

## Blockers
- **Sandbox cannot reach Postgres.** Sandbox netns has only loopback (host-published 127.0.0.1:5432 is
  unreachable) and AF_UNIX socket creation is denied (`PermissionError: Operation not permitted`), so
  sandboxed python/dbt/pytest cannot connect by TCP or a bind-mounted socket. Needs user decision.

## Next
Once DB access is resolved: run `tests/integration`, real ingestion of the 30 partitions, then Phase 2 (dbt).
