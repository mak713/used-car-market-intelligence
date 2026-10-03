/*
Business question
  How do listings first seen on each day (a "first-seen cohort") look, and how do their
  characteristics move over the observation window?
Why it matters
  Gives a time view (volume mix, reduction rate, days on market, reference value) for the BI
  trend visuals using the date dimension.
Techniques demonstrated
  Date-dimension join, cohort grouping, conditional aggregation, rolling windows (ROWS BETWEEN).
Data limitations
  The public sample exports at most ~1,000 rows per day and some days are much smaller, so DAILY
  COUNTS REFLECT THE SAMPLING, NOT MARKET ACTIVITY. Use the shares/medians, not the counts, for
  trends. Reference values are KBB range midpoints, not asking prices. Cross-sectional cohorts,
  not price histories.
*/
WITH daily AS (
    SELECT d.full_date,
           COUNT(*)                                                    AS listings,
           COUNT(*) FILTER (WHERE f.is_reduced_price)                  AS reduced,
           COUNT(*) FILTER (WHERE f.is_hot)                            AS hot,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.days_on_market) AS median_dom,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.reference_value_midpoint)
               FILTER (WHERE f.is_market_value_eligible)               AS median_ref_value
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_date d ON d.date_key = f.first_seen_date_key
    GROUP BY d.full_date
)
SELECT full_date, listings,
       ROUND(100.0 * reduced / listings, 1) AS reduced_pct,
       ROUND(100.0 * hot / listings, 1)     AS hot_pct,
       median_dom,
       ROUND(median_ref_value::numeric, 0)  AS median_ref_value,
       ROUND(100.0 * SUM(reduced) OVER w / SUM(listings) OVER w, 1) AS reduced_pct_7d_rolling,
       ROUND((AVG(median_ref_value) OVER w)::numeric, 0)                       AS median_ref_value_7d_avg,
       SUM(listings) OVER w                                         AS listings_7d_rolling
FROM daily
WINDOW w AS (ORDER BY full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
ORDER BY full_date;
