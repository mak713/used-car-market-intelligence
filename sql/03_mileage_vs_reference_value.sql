/*
Business question
  How does reference value differ across mileage bands for comparable vehicles?
Why it matters
  Quantifies the cross-sectional relationship between odometer reading and value level.
Techniques demonstrated
  Bucketing (mileage_bucket), cohort normalisation, PERCENTILE_CONT, LAG() over partitions.
Data limitations
  CROSS-SECTIONAL ONLY: different cars at different mileages observed in the same window. This is not
  a depreciation curve and says nothing about how any one vehicle's value changed over time. Each
  listing's reference value is indexed to the median of its make/model/model-year cohort (>= 8
  listings) so bands are comparable; bands need >= 30 listings.
*/
WITH cohort AS (
    SELECT v.make_name, v.model_name, v.year, v.body_style,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.reference_value_midpoint) AS cohort_median,
           COUNT(*) AS n
    FROM warehouse.fct_listings f JOIN warehouse.dim_vehicle v USING (vehicle_key)
    WHERE f.is_market_value_eligible
    GROUP BY v.make_name, v.model_name, v.year, v.body_style
    HAVING COUNT(*) >= 8
),
indexed AS (
    SELECT c.body_style, f.mileage_bucket, f.mileage_bucket_order,
           f.reference_value_midpoint / c.cohort_median AS value_index
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_vehicle v USING (vehicle_key)
    JOIN cohort c ON c.make_name = v.make_name AND c.model_name = v.model_name
                 AND c.year = v.year AND c.body_style IS NOT DISTINCT FROM v.body_style
    WHERE f.is_market_value_eligible AND f.mileage_bucket IS NOT NULL
),
by_band AS (
    SELECT body_style, mileage_bucket, mileage_bucket_order, COUNT(*) AS listings,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value_index) AS median_value_index
    FROM indexed
    GROUP BY body_style, mileage_bucket, mileage_bucket_order
    HAVING COUNT(*) >= 30
)
SELECT body_style, mileage_bucket, listings,
       ROUND(median_value_index::numeric, 3) AS median_value_index,
       ROUND((median_value_index - LAG(median_value_index) OVER w)::numeric, 3) AS change_vs_previous_band
FROM by_band
WINDOW w AS (PARTITION BY body_style ORDER BY mileage_bucket_order)
ORDER BY body_style, mileage_bucket_order;
