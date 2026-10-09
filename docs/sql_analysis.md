# Advanced SQL analyses

Eight PostgreSQL analyses over the `warehouse` schema (`sql/01_…` – `sql/08_…`). Each file opens with its
business question, why it matters, techniques, and data limitations. Run one with
`.venv/bin/python -m src.db.run_sql sql/01_vehicle_reference_value_benchmarks.sql`.

**Data honesty.** "Reference value" is the midpoint of the source's KBB fair-price range; it is **not** a
listing or asking price (`salePrice` is redacted in the public sample). Mileage analysis is cross-sectional.
Daily counts in the cohort trend reflect the sample's per-day cap, not market activity.

| # | File | Techniques | Rows returned* |
|---|------|------------|-------|
| 1 | `01_vehicle_reference_value_benchmarks` | CTEs, joins, `PERCENTILE_CONT`, cohort filter (n>=15) | 282 |
| 2 | `02_trim_reference_value_premiums` | multi-stage CTEs, baseline, % delta, `RANK` | 18 |
| 3 | `03_mileage_vs_reference_value` | bucketing, cohort index, `LAG` over partitions | 24 |
| 4 | `04_slow_moving_inventory` | percentiles, `FILTER`, `RANK`, min sample | 195 |
| 5 | `05_regional_reference_value_index` | mix-adjusted index, multi-stage CTEs, `RANK` | 30 |
| 6 | `06_reduced_price_listing_profile` | `FILTER`, `GROUPING SETS` | 9 |
| 7 | `07_seller_concentration_by_state` | shares, `RANK`, cumulative window sum, HHI | 32 |
| 8 | `08_first_seen_cohort_trends` | date dimension, cohorts, rolling windows | 30 |

\*Row counts and results measured on the warehouse built from source revision `1e325fd8…` (22,098 fact listings); the warehouse has since been refreshed to 23,950 listings, so re-running will give slightly different values. All eight execute and
return non-empty results (`tests/integration/test_sql_analyses.py`). Result sanity: e.g. the mileage index falls
monotonically with mileage for sedans/SUVs/trucks (SUV 0–24k 1.019 → 150k+ 0.641); trim premiums are positive for
top trims (F-150 2023 Lariat +17.5%). These are descriptive, cross-sectional observations only.

## EXPLAIN (ANALYZE, BUFFERS) — query 05 (what PostgreSQL actually chose)

Plans are saved in `docs/explain/`. As first written, query 05 joined the national cohort medians to listings on a
three-column key (make, model, year). PostgreSQL's estimate for that join was **1 row** (actual: 10,422), so it
planned the next join to `dim_geography` as a **Nested Loop with a join filter**, which discarded 43,532,701
rows and took **6,019 ms**. (`docs/explain/05_before_row_comparison_join.txt`). Rewriting the three-column join as
explicit equalities did *not* fix it (4,883 ms; `05_after_equality_join.txt` — the mis-estimate remains). Restructuring
the query so the large fact/dimension joins are resolved first in a `MATERIALIZED` CTE (single-key hash joins) and the
small cohort table is joined last gave **Hash Joins throughout, 67.5 ms** (`05_after_restructured.txt`), the same 30
result rows. Tables were already analyzed (autovacuum), so stale statistics were not the cause; the multi-column
correlated join estimate was. Timings are single runs on a local container (warm cache), not a benchmark.
