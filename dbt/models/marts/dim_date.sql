-- Grain: one calendar date covering the source observation range (all listing types).
with bounds as (
    select
        least(min(first_seen_at::date), min(source_file_date))   as d0,
        greatest(max(last_seen_at::date), max(source_file_date)) as d1
    from {{ ref('int_listings_deduped') }}
),
days as (select generate_series(d0, d1, interval '1 day')::date as full_date from bounds)
select
    to_char(full_date, 'YYYYMMDD')::int  as date_key,
    full_date,
    extract(day from full_date)::int     as day_of_month,
    extract(isodow from full_date)::int  as day_of_week,
    to_char(full_date, 'FMDay')          as day_name,
    extract(week from full_date)::int    as iso_week,
    extract(month from full_date)::int   as month_number,
    to_char(full_date, 'FMMonth')        as month_name,
    extract(quarter from full_date)::int as quarter,
    extract(year from full_date)::int    as year,
    extract(isodow from full_date) in (6, 7) as is_weekend
from days
