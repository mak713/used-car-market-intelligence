CREATE TABLE IF NOT EXISTS raw.autotrader_records (
    primary_key       text PRIMARY KEY,        -- source _primaryKey
    listing_id        text NOT NULL,
    first_seen_at     timestamptz NOT NULL,
    last_seen_at      timestamptz NOT NULL,
    source_file       text NOT NULL,
    source_file_date  date NOT NULL,
    record_hash       text NOT NULL,
    payload           jsonb NOT NULL,
    ingested_at       timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_raw_autotrader_listing_id ON raw.autotrader_records (listing_id);
