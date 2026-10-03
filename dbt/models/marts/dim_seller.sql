-- Grain: one seller_id (Type 1: latest observed attributes). NULL seller_id -> single 'Unknown' member.
with listings as (
    select * from {{ ref('int_listings_enriched') }}
    where listing_type in {{ var('fact_listing_types') }}
),
latest as (
    select l.*, row_number() over (partition by seller_id order by last_seen_at desc, listing_id desc) as rn
    from listings l
)
select
    {{ surrogate_key(['seller_id']) }} as seller_key,
    seller_id,
    seller_id is null                  as is_unknown_seller,
    is_private_seller,
    seller_contract_level,
    seller_review_count                as latest_review_count
from latest where rn = 1
