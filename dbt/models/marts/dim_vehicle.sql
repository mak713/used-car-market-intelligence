-- Grain: one vehicle CONFIGURATION (not a physical car; VIN is redacted in the source).
-- kbbVehicleId is NOT a stable configuration key in this source (one id spans several trims/engines,
-- occasionally models), so the key is a deterministic surrogate over the configuration attributes;
-- kbb_vehicle_id is kept as the latest observed attribute.
with listings as (
    select * from {{ ref('int_listings_enriched') }}
    where listing_type in {{ var('fact_listing_types') }}
),
keyed as (
    select
        {{ surrogate_key(['vehicle_year','make_name','model_name','trim','body_style','engine',
                          'drivetrain','transmission_group','fuel_type_group']) }} as vehicle_key,
        l.*,
        row_number() over (
            partition by {{ surrogate_key(['vehicle_year','make_name','model_name','trim','body_style','engine',
                                           'drivetrain','transmission_group','fuel_type_group']) }}
            order by last_seen_at desc, listing_id desc) as rn
    from listings l
)
select
    vehicle_key, kbb_vehicle_id, vehicle_year as year, make_code, make_name, model_code, model_name,
    trim, body_style, engine, displacement_liters, drivetrain, transmission_group, fuel_type_group,
    mpg_city, mpg_highway, kbb_consumer_rating, kbb_consumer_review_count
from keyed where rn = 1
