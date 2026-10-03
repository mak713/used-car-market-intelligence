# Architecture

```
Hugging Face daily Parquet partitions (rebrowser/autotrader-dataset)
   -> source discovery (Hub API: file list + LFS sha256 + repo revision)
   -> download only unseen/changed (name, sha256) and re-verify the hash
   -> contract validation of ALL files (before any write)
   -> per-file atomic load: COPY to temp table -> upsert raw.autotrader_records, checkpoint meta.processed_files
   -> dbt: staging (view) -> intermediate (dedupe, enrich) -> warehouse marts
   -> smoke checks -> meta.pipeline_runs summary
   -> advanced SQL (sql/) and Power BI (warehouse tables only)
```

Database `used_car_intelligence` (PostgreSQL 16, Docker Compose): schemas `raw`, `meta`, `staging`, `intermediate`, `warehouse`.

## Raw and metadata
- `raw.autotrader_records`: PK `primary_key` (source `_primaryKey`), `listing_id`, `first_seen_at`, `last_seen_at`,
  `source_file`, `source_file_date`, `record_hash` (sha256 of canonical JSON), full record as JSONB `payload`
  (premium placeholders are preserved — field extraction and NULL-ing happen in dbt), `ingested_at`, `updated_at`.
- `meta.processed_files`: PK (`source_file`, `content_hash`); source date, Hub revision, row counts, run id. Only
  successful file versions are recorded; a failed file rolls back and stays eligible.
- `meta.pipeline_runs`: one row per invocation — counters, `dbt_status`, `smoke_status`, `error_summary`.

## Upsert rule
Insert new keys. On conflict update only if `record_hash` differs **and** the incoming `last_seen_at` is not older
than the stored one (a stale revision never overwrites a newer observation). Identical records are no-ops
(not even `updated_at` changes). `first_seen_at` keeps the earliest value.

## dbt lineage
`raw.autotrader_records` -> `stg_autotrader_listings` -> `int_listings_deduped` (one row/listing via
`ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY last_seen_at DESC, source_file_date DESC, primary_key DESC)`,
plus `source_observation_count`) -> `int_listings_enriched` -> `fct_listings` + `dim_vehicle`, `dim_seller`,
`dim_geography` (+ `state_regions` seed), `dim_date`.

```
dim_vehicle ─┐
dim_seller  ─┼── fct_listings  (grain: one used/certified listing, latest observed record)
dim_geography┤
dim_date    ─┘   (first_seen / last_seen / source_file date keys)
```

## Orchestration
Prefect flow `used_car_market_pipeline`: `discover_source_files` -> `download_changed_files` (retries=2, 5 s) ->
`validate_source_files` -> `load_raw_records` -> `run_dbt_build` -> `run_pipeline_smoke_checks` -> `record_run_summary`.
Contract, load, dbt and smoke failures are not retried; the run row is marked `failed` with an error summary.
Run: `HF_HOME=$PWD/.cache/hf .venv/bin/python -m src.orchestration.flow [--revision SHA] [--source-dir DIR] [--date-from D --date-to D]`.
`--revision` pins the source for reproducible runs.

## Design decisions
- Listing scope: Used, Certified and Third-Party Certified (kept distinct); New excluded.
- `dim_vehicle` key is a deterministic surrogate over configuration attributes, because `kbbVehicleId` is not a
  stable configuration key in this source (measured). `kbb_vehicle_id` is retained as an attribute.
- Unknown seller member for the 13 rows with no `sellerId`.
- Reference value fields (midpoint/spread/spread %) are NULL unless the KBB low/high pair is valid (low > 0, high >= low).
