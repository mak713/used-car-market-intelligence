/*
Business question
  Which states/regions list vehicles whose reference value sits above or below the national level,
  after controlling for what kind of vehicle they list?
Why it matters
  A raw regional average mostly reflects vehicle mix (more trucks, newer cars). Indexing each listing
  to its own make/model/model-year national median removes most of that mix effect.
Techniques demonstrated
  Multi-stage CTEs, cohort-normalised (mix-adjusted) index, geography dimension + seed-based regions,
  PERCENTILE_CONT, RANK() window.
Data limitations
  Reference value is the KBB range midpoint (not an asking price). Adjustment only controls for
  make/model/year (not trim, mileage or condition). National cohorts need >= 10 listings; states
  need >= 50 indexed listings. Small states drop out of the sample.
*/
WITH national AS (
    SELECT v.make_name, v.model_name, v.year,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.reference_value_midpoint) AS national_median
    FROM warehouse.fct_listings f JOIN warehouse.dim_vehicle v USING (vehicle_key)
    WHERE f.is_market_value_eligible
    GROUP BY v.make_name, v.model_name, v.year
    HAVING COUNT(*) >= 10
),
listing_base AS MATERIALIZED (   -- resolve the large fact/dimension joins first (hash joins on single keys)
    SELECT g.region, g.state_code, v.make_name, v.model_name, v.year, f.reference_value_midpoint
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_vehicle v   USING (vehicle_key)
    JOIN warehouse.dim_geography g USING (geography_key)
    WHERE f.is_market_value_eligible AND g.state_code IS NOT NULL
),
indexed AS (
    SELECT b.region, b.state_code, b.reference_value_midpoint / n.national_median AS value_index
    FROM listing_base b
    JOIN national n ON n.make_name = b.make_name AND n.model_name = b.model_name AND n.year = b.year
),
by_state AS (
    SELECT region, state_code, COUNT(*) AS listings,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value_index) AS median_value_index
    FROM indexed
    GROUP BY region, state_code
    HAVING COUNT(*) >= 50
)
SELECT region, state_code, listings,
       ROUND(median_value_index::numeric, 3) AS median_value_index,
       ROUND(((median_value_index - 1) * 100)::numeric, 1) AS pct_vs_national,
       RANK() OVER (ORDER BY median_value_index DESC) AS state_rank
FROM by_state
ORDER BY state_rank;
