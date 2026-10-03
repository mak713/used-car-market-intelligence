/*
Business question
  Which make/model cohorts hold a disproportionate share of slow-moving listings (long days on market)?
Why it matters
  Identifies segments where inventory sits, a proxy for weak demand or aggressive positioning.
Techniques demonstrated
  PERCENTILE_CONT percentiles, cohort logic, FILTER aggregates, RANK() with minimum sample sizes.
Data limitations
  days_on_market is as reported by the source at the last observation, and the sample is capped per
  day, so cohort shares are indicative, not market-wide. "Slow-moving" is defined here as
  days_on_market >= 60. Reference values (not asking prices) are only used for context. Cohorts need
  >= 25 listings.
*/
WITH cohort AS (
    SELECT v.make_name, v.model_name,
           COUNT(*)                                                        AS listings,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.days_on_market)   AS dom_p50,
           PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY f.days_on_market)   AS dom_p90,
           COUNT(*) FILTER (WHERE f.days_on_market >= 60)                  AS slow_listings,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.reference_value_midpoint)
               FILTER (WHERE f.is_market_value_eligible)                   AS median_ref_value
    FROM warehouse.fct_listings f JOIN warehouse.dim_vehicle v USING (vehicle_key)
    WHERE f.days_on_market IS NOT NULL
    GROUP BY v.make_name, v.model_name
    HAVING COUNT(*) >= 25
)
SELECT RANK() OVER (ORDER BY slow_listings::numeric / listings DESC) AS slow_share_rank,
       make_name, model_name, listings, slow_listings,
       ROUND(100.0 * slow_listings / listings, 1) AS slow_share_pct,
       dom_p50, dom_p90,
       ROUND(median_ref_value::numeric, 0) AS median_ref_value
FROM cohort
ORDER BY slow_share_rank, listings DESC;
