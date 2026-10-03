/*
Business question
  Within a model and model year, which trims carry the highest reference-value premium over the
  model-year baseline?
Why it matters
  Shows how much of a model's value spread is explained by trim level, ranking trims by premium.
Techniques demonstrated
  Multi-stage CTEs, baseline vs. cohort comparison, percentage deltas, RANK() window.
Data limitations
  Reference value is the KBB range midpoint, not an asking price. Trim medians are NOT adjusted for
  mileage or condition, so a premium partly reflects mix (newer/lower-mileage cars). Trims need >= 10
  listings and the model-year baseline needs >= 3 qualifying trims.
*/
WITH eligible AS (
    SELECT v.make_name, v.model_name, v.year, v.trim, f.reference_value_midpoint AS ref_mid
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_vehicle v USING (vehicle_key)
    WHERE f.is_market_value_eligible AND v.trim IS NOT NULL
),
trim_stats AS (
    SELECT make_name, model_name, year, trim, COUNT(*) AS listings,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ref_mid) AS trim_median
    FROM eligible
    GROUP BY make_name, model_name, year, trim
    HAVING COUNT(*) >= 10
),
baseline AS (
    SELECT make_name, model_name, year,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY trim_median) AS baseline_median,
           COUNT(*) AS trims_in_cohort
    FROM trim_stats
    GROUP BY make_name, model_name, year
    HAVING COUNT(*) >= 3
)
SELECT t.make_name, t.model_name, t.year, t.trim, t.listings,
       ROUND(t.trim_median::numeric, 0)   AS trim_median_ref_value,
       ROUND(b.baseline_median::numeric, 0) AS model_year_baseline,
       ROUND(((t.trim_median / b.baseline_median - 1) * 100)::numeric, 1) AS premium_pct,
       RANK() OVER (PARTITION BY t.make_name, t.model_name, t.year ORDER BY t.trim_median DESC) AS trim_rank
FROM trim_stats t
JOIN baseline b USING (make_name, model_name, year)
ORDER BY premium_pct DESC, t.make_name, t.model_name;
