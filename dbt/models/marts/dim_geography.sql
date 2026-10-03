-- Grain: unique ZIP / city / state combination, with a broad region from a seed (no external API).
with combos as (
    select distinct seller_zip as zip_code, seller_city as city, seller_state as state_code
    from {{ ref('int_listings_enriched') }}
    where listing_type in {{ var('fact_listing_types') }}
)
select
    {{ surrogate_key(['c.zip_code','c.city','c.state_code']) }} as geography_key,
    c.zip_code, c.city, c.state_code,
    r.state_name,
    coalesce(r.region, 'Unknown') as region
from combos c
left join {{ ref('state_regions') }} r on r.state_code = c.state_code
