/*
Business question
  How do listings flagged "price reduced" differ from the rest (mileage, days on market, reference
  value, age)?
Why it matters
  Profiles the kind of inventory dealers cut prices on, without needing the (redacted) asking price.
Techniques demonstrated
  Conditional aggregation with FILTER, GROUPING SETS, PERCENTILE_CONT.
Data limitations
  is_reduced_price is a source flag; the size or date of the reduction is unknown. Reference value is
  the KBB range midpoint, not an asking price. Only market-value-eligible listings feed the reference
  value columns. Associations only; no causal claim.
*/
SELECT COALESCE(f.listing_type, 'ALL TYPES')                      AS listing_type,
       CASE WHEN f.is_reduced_price IS NULL THEN 'ALL' WHEN f.is_reduced_price THEN 'reduced' ELSE 'not reduced' END AS price_flag,
       COUNT(*)                                                   AS listings,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.mileage)            AS median_mileage,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.days_on_market)     AS median_days_on_market,
       ROUND(AVG(f.vehicle_age_years)::numeric, 2)                AS avg_age_years,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.reference_value_midpoint)
             FILTER (WHERE f.is_market_value_eligible)::numeric, 0) AS median_ref_value,
       ROUND(100.0 * COUNT(*) FILTER (WHERE f.days_on_market >= 60) / COUNT(*), 1) AS pct_dom_60_plus,
       ROUND(100.0 * COUNT(*) FILTER (WHERE f.mileage >= 100000) / COUNT(*), 1)    AS pct_mileage_100k_plus,
       ROUND(100.0 * COUNT(*) FILTER (WHERE f.vehicle_age_years >= 8) / COUNT(*), 1) AS pct_age_8_plus
FROM warehouse.fct_listings f
GROUP BY GROUPING SETS ((f.listing_type, f.is_reduced_price), (f.is_reduced_price), ())
ORDER BY f.listing_type NULLS LAST, f.is_reduced_price NULLS LAST;
