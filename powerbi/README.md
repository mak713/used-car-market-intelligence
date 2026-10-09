# Power BI report

`Used_Car_Market_Intelligence.pbix` is the finished three-page report (screenshots in `../docs/images/`). It was built
in Power BI Desktop (Windows), refreshed successfully against the latest warehouse state and visually reviewed. The
sections below document the connection, model, page design and measure checks so the report can be rebuilt or
refreshed. The `.pbix` embeds the imported data (CC BY-NC 4.0 — see root README attribution).

## 1. Connect (Windows Power BI Desktop, Import mode)

1. Start the database from WSL: `docker compose up -d` (repo root). Postgres is published on `127.0.0.1:5432`
   (Docker Desktop forwards it to Windows `localhost:5432`).
2. Power BI Desktop > Get data > **PostgreSQL database** > Server `localhost:5432`, Database
   `used_car_intelligence`, **Import**. Credentials: *Database* tab, user/password from your local `.env`
   (`.env.example` shows the dev defaults). If Desktop asks for the Npgsql provider, install it, then retry.
3. In the Navigator, tick **only** these `warehouse` tables: `fct_listings`, `dim_vehicle`, `dim_seller`,
   `dim_geography`, `dim_date`. Do **not** import `raw`, `meta`, `staging`, `intermediate` or `state_regions`.

## 2. Model

| From (1) | To (*) | Column | Filter | Active |
|---|---|---|---|---|
| `dim_vehicle[vehicle_key]` | `fct_listings[vehicle_key]` | | single (dim -> fact) | yes |
| `dim_seller[seller_key]` | `fct_listings[seller_key]` | | single | yes |
| `dim_geography[geography_key]` | `fct_listings[geography_key]` | | single | yes |
| `dim_date[date_key]` | `fct_listings[first_seen_date_key]` | primary date relationship | single | **yes** |
| `dim_date[date_key]` | `fct_listings[last_seen_date_key]` | | single | no (use `USERELATIONSHIP`) |
| `dim_date[date_key]` | `fct_listings[source_file_date_key]` | | single | no |

- Mark `dim_date` as a date table (column `full_date`). Hide the key columns on `fct_listings`.
- Sort `fct_listings[mileage_bucket]` by `mileage_bucket_order`, and `days_on_market_bucket` by
  `days_on_market_bucket_order`. Sort `dim_date[month_name]` by `month_number`, `day_name` by `day_of_week`.
- Rename for display (honesty): `kbb_fair_price_low/high` -> **Reference Value Low (KBB)** / **High (KBB)**;
  `reference_value_midpoint` -> **Reference Value (KBB midpoint)**. Never "Price" / "Average Listing Price".
- Add the measures from `dax_measures.dax`.

## 3. Pages and visuals

**Page 1 — Market Overview** (slicers: listing type, region/state, first-seen date)
- KPI cards: Listing Count, Median Reference Value, Median Mileage, Median Days on Market, Reduced Price Rate,
  Certified Inventory Share.
- Map or bar: Listing Count by `dim_geography[state_code]` (or filled map).
- Bar: top 15 `dim_vehicle[make_name]` by Listing Count.
- Donut/column: Listing Count by `dim_vehicle[body_style]`.
- Histogram-style column chart: Listing Count by reference-value band (create a binned group on
  `reference_value_midpoint`, e.g. $5,000 bins). Footnote: "Reference value = midpoint of KBB fair-price range."

**Page 2 — Vehicle Value & Mileage** (slicers: make, body style, model year, mileage bucket)
- Scatter: X `mileage`, Y `reference_value_midpoint`, details `listing_id`, colour `body_style` (cross-sectional; title it so).
- Matrix: rows `make_name` > `model_name` > `trim`; values Listing Count, Median Reference Value, Median Mileage.
- Bar: Trim Premium % by `trim` (visual filter: Listing Count >= 10, one make/model/year selected).
- Box-like column: Median Days on Market by `body_style` and by `mileage_bucket`.

**Page 3 — Market Dynamics & Sellers** (slicers: state, listing type)
- Line: Listing Count / Reduced Price Rate / Median Reference Value by `dim_date[full_date]` (first-seen cohort).
  Add a text note: daily counts reflect the sample cap (<=1,000 rows/day), not market activity — read rates/medians.
- Clustered column: reduced vs not reduced (`is_reduced_price`) — Median Mileage, Median Days on Market,
  Median Reference Value, Slow-Moving Share.
- Bar: top 10 `dim_seller[seller_id]` by Listing Count (visual filter `is_unknown_seller` = false), with Top 5 Seller Share card.
- Table: slow-moving cohorts — `make_name`, `model_name`, Listing Count, Median Days on Market, Slow-Moving Share
  (visual filter Listing Count >= 25, sort by Slow-Moving Share desc). Compare with `sql/04`.

## 4. Measure checks (no slicers)

The report shows the **latest refreshed** values (35 partitions, revision `f9511a90…`). The original 30-partition values are kept for reference (`docs/acceptance_results.md`).


| Measure | Latest refresh (report) | Original 30-partition build |
|---|---|---|
| Listing Count | 23,950 | 22,098 |
| Market-Value Eligible Listings | 21,611 | 19,869 |
| Median Reference Value | 27,043 | 27,210 |
| Median Mileage | 43,819.5 | 43,750.5 |
| Median Days on Market | 12 | 12 |
| Reduced Price Rate | 22.58% | 22.32% |
| Hot Listing Rate | 2.79% | 2.79% |
| Certified Inventory Share | 14.55% | 14.68% |
| Median Reference-Value Spread | 2,600 | 2,600 |
| Listings with a known seller | 23,935 (15 Unknown-seller facts) | 22,085 |
| First-seen date range | 2026-08-21 – 2026-09-24 | 2026-08-21 – 2026-09-19 |

## 5. Refresh procedure and status

Refresh test **passed**: after the pipeline loaded the 5 newly published partitions, Home > Refresh succeeded with
only the five `warehouse` tables, and the values in section 4 matched.

To refresh again: start Postgres (`docker compose up -d`), run `HF_HOME=$PWD/.cache/hf .venv/bin/python -m
src.orchestration.flow`, then Home > Refresh in Desktop. Model checks: only the five `warehouse` tables are
imported and all relationships are single-direction.
