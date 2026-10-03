-- fct_listings must equal the number of distinct used/certified listing_ids in the staged data.
with expected as (
    select count(distinct listing_id) as n from {{ ref('stg_autotrader_listings') }}
    where listing_type in {{ var('fact_listing_types') }}
),
actual as (select count(*) as n from {{ ref('fct_listings') }})
select e.n as expected_rows, a.n as fact_rows from expected e, actual a where e.n <> a.n
