/*
Business question
  How concentrated is listing supply among sellers within each state?
Why it matters
  Highly concentrated states depend on a few dealers, which affects how representative state-level
  market statistics are.
Techniques demonstrated
  Seller share via window SUM, RANK(), running (cumulative) share, top-N concentration, HHI.
Data limitations
  Seller identity is a numeric seller_id only (names are redacted). Listings with no seller_id
  (Unknown seller) are excluded. Based on listings present in the sample, not true inventory.
  States need >= 100 listings with a known seller.
*/
WITH seller_state AS (
    SELECT g.state_code, s.seller_id, COUNT(*) AS listings
    FROM warehouse.fct_listings f
    JOIN warehouse.dim_seller s    USING (seller_key)
    JOIN warehouse.dim_geography g USING (geography_key)
    WHERE NOT s.is_unknown_seller AND g.state_code IS NOT NULL
    GROUP BY g.state_code, s.seller_id
),
shares AS (
    SELECT state_code, seller_id, listings,
           listings::numeric / SUM(listings) OVER (PARTITION BY state_code) AS share,
           SUM(listings) OVER (PARTITION BY state_code)                     AS state_listings,
           RANK() OVER (PARTITION BY state_code ORDER BY listings DESC, seller_id) AS seller_rank
    FROM seller_state
),
cumulative AS (
    SELECT *, SUM(share) OVER (PARTITION BY state_code ORDER BY seller_rank
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_share
    FROM shares
)
SELECT state_code,
       MAX(state_listings)                             AS listings,
       COUNT(*)                                        AS sellers,
       ROUND(100 * MAX(share), 1)                      AS top1_share_pct,
       ROUND(100 * MAX(cum_share) FILTER (WHERE seller_rank <= 5), 1) AS top5_share_pct,
       ROUND((10000 * SUM(share * share))::numeric, 0) AS hhi
FROM cumulative
GROUP BY state_code
HAVING MAX(state_listings) >= 100
ORDER BY hhi DESC;
