-- One row per listing_id: the latest observed record. source_observation_count = raw rows seen for it.
with ranked as (
    select
        s.*,
        row_number() over (
            partition by listing_id
            order by last_seen_at desc, source_file_date desc, primary_key desc
        ) as observation_rank,
        count(*) over (partition by listing_id) as source_observation_count
    from {{ ref('stg_autotrader_listings') }} s
)
select * from ranked where observation_rank = 1
