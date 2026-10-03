-- Model years: nothing before 1980, nothing beyond next model year + 1 relative to the observation.
select v.vehicle_key, v.year
from {{ ref('dim_vehicle') }} v
where v.year < 1980 or v.year > (select extract(year from max(last_seen_at))::int + 1 from {{ ref('fct_listings') }})
