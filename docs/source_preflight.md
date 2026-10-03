# Source preflight (Phase 0)

Checked 2026-10-03 against `rebrowser/autotrader-dataset` on Hugging Face, repo revision
`1e325fd8d9d05895fc2d26a2eac5a36f3ef07487` (last modified 2026-10-03).

## Terms
- Dataset card license: **CC BY-NC 4.0** — "free for research and non-commercial use with attribution";
  commercial use needs a paid Rebrowser license; governed also by the Rebrowser Terms of Use.
- Preview sample of Rebrowser's larger dataset. Nothing was purchased and no premium data was used.

## Layout
- `car-listings/data/YYYY-MM-DD.parquet` (+ a CSV twin per day, unused) and `car-listings/schema.json`.
- 30 Parquet partitions, 2026-08-21 … 2026-09-19. Card: "one file per day, up to 1,000 rows each, last 30 days
  retained" — older partitions roll off, so local history must never be deleted when they disappear.
- Partition date equals the `_firstSeenAt` date for every row. Files are revised after publication
  (`_lastSeenAt` reaches 2026-10-01 inside older partitions), so file identity = filename + content hash
  (Hub LFS sha256), not filename alone.

## Schema (measured from the Parquet files; one identical schema in all 30 files; 71 columns)
Matches the card/`schema.json`. Actual Arrow types differ from the card's "float": `year` uint16, `mileage` uint32,
`daysOnMarket` int16, `sellerId`/`kbbVehicleId` uint64 (nullable), `kbbFairPriceLow/High` double,
`displacementUOM`/`kbbConsumerRatings` float32, timestamps `timestamp[ms, UTC]`, flags bool.
Premium/redacted fields (all values the string `[PREMIUM]`): `vin`, `salePrice`, `kbbFairPurchasePrice`,
`sellerName`, `sellerPhone`, `sellerRating`, `sellerWebsite`, `images`, `listingUrl`.

## Findings (24,608 rows total)
| Check | Result |
|---|---|
| `salePrice`, `vin` usable? | **No — 100% `[PREMIUM]`.** No actual listing price analysis, no VIN/NHTSA enrichment in V1. |
| `kbbFairPriceLow/High` numeric | Yes. Null in 1,764 rows; low = 0 in 1,316 rows (invalid -> not value-eligible); low > high in 0 rows. |
| Identifiers | `_primaryKey` == `listingId` for every row; 24,608 distinct. **Zero overlap across the 30 files.** |
| Timestamps | `_firstSeenAt`/`_lastSeenAt` populated; last_seen >= first_seen everywhere. |
| Listing types | Used 18,855; Certified 2,918; Third-Party Certified 325; New 2,510 (New excluded from the fact). |
| `sellerId` | 8,460 distinct; **13 rows null** (-> Unknown seller member). |
| `kbbVehicleId` | null 1,212, value 0 in 897 (treated as absent). **Not a stable configuration key**: 1,414 of 9,268 ids span >1 full vehicle configuration. |
| Years / mileage / DOM | year 1987–2027; mileage 0–435,413; days on market 0–1,038; none negative. |
| Daily partition sizes | 17 – 1,000 rows (sample is capped; 2026-09-03…09-07 and 09-19 are small). |

## Mapping / adaptations
No field renames were needed. Contract = the 46 columns dbt staging reads (extra columns are allowed, a missing or
mistyped required column fails the file before any raw write).
