-- No kept record may be older than another observation of the same listing in staging.
select d.listing_id from {{ ref('int_listings_deduped') }} d
join {{ ref('stg_autotrader_listings') }} s on s.listing_id = d.listing_id and s.last_seen_at > d.last_seen_at
