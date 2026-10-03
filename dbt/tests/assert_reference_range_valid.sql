-- Eligible listings need low <= high and a midpoint inside the range; midpoint/spread are NULL otherwise.
select listing_id from {{ ref('fct_listings') }}
where (is_market_value_eligible and (kbb_fair_price_low > kbb_fair_price_high
         or reference_value_midpoint < kbb_fair_price_low or reference_value_midpoint > kbb_fair_price_high
         or kbb_fair_price_low <= 0))
   or (not is_market_value_eligible and (reference_value_midpoint is not null or reference_value_spread is not null))
