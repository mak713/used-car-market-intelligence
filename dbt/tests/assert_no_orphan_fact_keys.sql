select f.listing_id from {{ ref('fct_listings') }} f
left join {{ ref('dim_vehicle') }} v using (vehicle_key)
left join {{ ref('dim_seller') }} s using (seller_key)
left join {{ ref('dim_geography') }} g using (geography_key)
left join {{ ref('dim_date') }} d on d.date_key = f.first_seen_date_key
where v.vehicle_key is null or s.seller_key is null or g.geography_key is null or d.date_key is null
