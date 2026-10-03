-- Derived analytics fields. Reference value = midpoint of the source-provided KBB fair-price range
-- (NOT a listing/asking price). Only computed when the low/high pair is valid.
with base as (
    select
        d.*,
        (kbb_fair_price_low is not null and kbb_fair_price_high is not null
         and kbb_fair_price_low > 0 and kbb_fair_price_high >= kbb_fair_price_low) as is_market_value_eligible
    from {{ ref('int_listings_deduped') }} d
)
select
    base.*,
    greatest(extract(year from last_seen_at)::int - vehicle_year, 0)                    as vehicle_age_years,
    case when is_market_value_eligible then (kbb_fair_price_low + kbb_fair_price_high) / 2 end
                                                                                        as reference_value_midpoint,
    case when is_market_value_eligible then kbb_fair_price_high - kbb_fair_price_low end as reference_value_spread,
    case when is_market_value_eligible
         then round((kbb_fair_price_high - kbb_fair_price_low)
                    / ((kbb_fair_price_low + kbb_fair_price_high) / 2), 4) end           as reference_value_spread_pct,
    case when mileage is null then null
         when mileage < 25000 then '0-24k'  when mileage < 50000 then '25-49k'
         when mileage < 75000 then '50-74k' when mileage < 100000 then '75-99k'
         when mileage < 150000 then '100-149k' else '150k+' end                          as mileage_bucket,
    case when mileage is null then null
         when mileage < 25000 then 1  when mileage < 50000 then 2 when mileage < 75000 then 3
         when mileage < 100000 then 4 when mileage < 150000 then 5 else 6 end            as mileage_bucket_order,
    case when days_on_market is null then null
         when days_on_market <= 7 then '0-7d'   when days_on_market <= 14 then '8-14d'
         when days_on_market <= 30 then '15-30d' when days_on_market <= 60 then '31-60d'
         when days_on_market <= 90 then '61-90d' else '91d+' end                         as days_on_market_bucket,
    case when days_on_market is null then null
         when days_on_market <= 7 then 1  when days_on_market <= 14 then 2 when days_on_market <= 30 then 3
         when days_on_market <= 60 then 4 when days_on_market <= 90 then 5 else 6 end    as days_on_market_bucket_order
from base
