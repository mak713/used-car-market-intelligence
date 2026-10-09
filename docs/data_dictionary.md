# Data dictionary (`warehouse` schema)

**Reference value** = midpoint of the source-provided KBB fair-price range (`kbb_fair_price_low`/`high`). It is not a
listing, asking or sale price (`salePrice` is redacted in the public sample).

## fct_listings — one used/certified listing (latest observed record); 23,950 rows in the final refreshed state
| Column | Meaning |
|---|---|
| `listing_id` | Source listing id (PK; unique, not null) |
| `latest_primary_key` | `_primaryKey` of the observation kept |
| `vehicle_key`, `seller_key`, `geography_key` | FKs to dimensions |
| `first_seen_date_key`, `last_seen_date_key`, `source_file_date_key` | FKs to `dim_date` (YYYYMMDD); first_seen is the primary relationship |
| `first_seen_at`, `last_seen_at` | Source timestamps (UTC) |
| `listing_type` | `Used`, `Certified`, `Third-Party Certified` |
| `mileage`, `days_on_market` | As reported by the source |
| `kbb_fair_price_low/high` | KBB fair-price range bounds (raw; 0 and NULL occur) |
| `reference_value_midpoint/spread/spread_pct` | Derived from the range; NULL unless `is_market_value_eligible` |
| `deal_indicator` | KBB deal rating where present (Great/Good; NULL otherwise) |
| `exterior_color`, `interior_color` | Simplified colour names |
| `is_hot`, `is_newly_listed`, `is_reduced_price`, `is_no_haggle_price`, `has_special_offer` | Source flags |
| `priority`, `has_leather_seats` | Source listing tier; leather flag |
| `options_count`, `images_count`, `safety_recall_count` | Source counts |
| `source_observation_count` | Raw rows observed for this listing (1 for all real data) |
| `vehicle_age_years` | max(year(last_seen_at) − model year, 0) |
| `mileage_bucket(_order)`, `days_on_market_bucket(_order)` | Bucket labels and sort keys |
| `is_market_value_eligible` | KBB low > 0, high >= low, both present |

## dim_vehicle — one vehicle configuration (not a physical car); 11,013 rows
`vehicle_key` (md5 of year/make/model/trim/body/engine/drivetrain/transmission/fuel), `kbb_vehicle_id` (latest
observed; not a key), `year`, `make_code/name`, `model_code/name`, `trim`, `body_style`, `engine`, `displacement_liters`,
`drivetrain`, `transmission_group`, `fuel_type_group`, `mpg_city/highway`, `kbb_consumer_rating`, `kbb_consumer_review_count`.

## dim_seller — one `seller_id`, Type 1 (latest observed); 8,191 rows
`seller_key`, `seller_id` (NULL only for the Unknown member), `is_unknown_seller`, `is_private_seller`,
`seller_contract_level`, `latest_review_count`. Seller names are redacted and not stored.

## dim_geography — one ZIP/city/state combination; 4,179 rows
`geography_key`, `zip_code`, `city`, `state_code`, `state_name`, `region` (Northeast/Midwest/South/West from the
`state_regions` seed; `Unknown` when state is missing).

## dim_date — one calendar date over the observation range; 42 rows (2026-08-21 … 2026-10-01)
`date_key` (YYYYMMDD), `full_date`, `day_of_month`, `day_of_week`, `day_name`, `iso_week`, `month_number`, `month_name`,
`quarter`, `year`, `is_weekend`.
