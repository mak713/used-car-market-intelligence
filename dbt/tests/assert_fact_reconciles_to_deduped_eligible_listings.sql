-- fct_listings is built from the latest deduplicated observation of each listing (int_listings_deduped),
-- keeping only the approved listing types. A listing whose latest observation is out of scope (e.g. New)
-- must be absent even if an older observation was in scope.
with expected as (
    select count(*) as n from {{ ref('int_listings_deduped') }}
    where listing_type in {{ var('fact_listing_types') }}
),
actual as (select count(*) as n from {{ ref('fct_listings') }})
select e.n as expected_rows, a.n as fact_rows from expected e, actual a where e.n <> a.n
