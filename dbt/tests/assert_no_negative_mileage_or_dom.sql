select listing_id from {{ ref('fct_listings') }} where mileage < 0 or days_on_market < 0
