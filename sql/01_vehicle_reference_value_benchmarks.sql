/*
Business question
  What does the KBB reference-value range look like for each make/model/model-year, and how
  dispersed is it?
Why it matters
  A benchmark per vehicle cohort is the baseline every other value comparison (trim premiums,
  regional index, mileage effects) is measured against.
Techniques demonstrated
  CTEs, fact-to-dimension joins, PERCENTILE_CONT (ordered-set aggregate), cohort-size filter (HAVING).
Data limitations
  "Reference value" = midpoint of the source-provided KBB fair-price range. It is NOT a listing or
  asking price (salePrice is redacted in the public sample). Only market-value-eligible listings
  (valid low/high pair, low > 0) are used. Cohorts under 15 listings are dropped. The sample is
  ~30 days of capped daily exports, so it is not a census of the market.
*/
WITH eligible AS (
    SELECT v.make_name, v.model_name, v.year, f.reference_value_midpoint AS ref_mid
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_vehicle v USING (vehicle_key)
    WHERE f.is_market_value_eligible
),
benchmarks AS (
    SELECT make_name, model_name, year,
           COUNT(*)                                                      AS listings,
           PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY ref_mid)         AS ref_value_p25,
           PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ref_mid)         AS ref_value_median,
           PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY ref_mid)         AS ref_value_p75
    FROM eligible
    GROUP BY make_name, model_name, year
    HAVING COUNT(*) >= 15
)
SELECT make_name, model_name, year, listings,
       ROUND(ref_value_p25::numeric, 0)     AS ref_value_p25,
       ROUND(ref_value_median::numeric, 0)  AS ref_value_median,
       ROUND(ref_value_p75::numeric, 0)     AS ref_value_p75,
       ROUND(((ref_value_p75 - ref_value_p25) / NULLIF(ref_value_median, 0))::numeric, 3) AS iqr_to_median
FROM benchmarks
ORDER BY listings DESC, make_name, model_name, year;
