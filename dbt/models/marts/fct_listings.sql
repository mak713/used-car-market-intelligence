-- Grain: one used/certified listing (latest valid observed record). New listings are excluded.
-- kbb_fair_price_low/high and reference_value_* are a KBB REFERENCE VALUE range, not a listing price.
select
    e.listing_id,
    e.primary_key                                                   as latest_primary_key,
    {{ surrogate_key(['e.vehicle_year','e.make_name','e.model_name','e.trim','e.body_style','e.engine',
                      'e.drivetrain','e.transmission_group','e.fuel_type_group']) }} as vehicle_key,
    {{ surrogate_key(['e.seller_id']) }}                            as seller_key,
    {{ surrogate_key(['e.seller_zip','e.seller_city','e.seller_state']) }} as geography_key,
    to_char(e.first_seen_at, 'YYYYMMDD')::int                       as first_seen_date_key,
    to_char(e.last_seen_at, 'YYYYMMDD')::int                        as last_seen_date_key,
    to_char(e.source_file_date, 'YYYYMMDD')::int                    as source_file_date_key,
    e.first_seen_at, e.last_seen_at,
    e.listing_type,
    e.mileage, e.days_on_market,
    e.kbb_fair_price_low, e.kbb_fair_price_high,
    e.reference_value_midpoint, e.reference_value_spread, e.reference_value_spread_pct,
    e.deal_indicator,
    e.exterior_color, e.interior_color,
    e.is_hot, e.is_newly_listed, e.is_reduced_price, e.is_no_haggle_price, e.has_special_offer,
    e.priority, e.has_leather_seats,
    e.options_count, e.images_count, e.safety_recall_count,
    e.source_observation_count,
    e.vehicle_age_years,
    e.mileage_bucket, e.mileage_bucket_order, e.days_on_market_bucket, e.days_on_market_bucket_order,
    e.is_market_value_eligible
from {{ ref('int_listings_enriched') }} e
where e.listing_type in {{ var('fact_listing_types') }}
