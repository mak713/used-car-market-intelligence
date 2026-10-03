CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    run_id            uuid PRIMARY KEY,
    started_at        timestamptz NOT NULL DEFAULT now(),
    finished_at       timestamptz,
    status            text NOT NULL DEFAULT 'running'
                      CHECK (status IN ('running', 'success', 'failed')),
    source_revision   text,
    files_discovered  integer NOT NULL DEFAULT 0,
    files_processed   integer NOT NULL DEFAULT 0,
    rows_read         bigint  NOT NULL DEFAULT 0,
    rows_inserted     bigint  NOT NULL DEFAULT 0,
    rows_updated      bigint  NOT NULL DEFAULT 0,
    rows_unchanged    bigint  NOT NULL DEFAULT 0,
    dbt_status        text,
    smoke_status      text,
    error_summary     text
);

-- One row per successfully committed source file version.
-- Failed loads roll back and never appear here, so they stay eligible for a rerun.
CREATE TABLE IF NOT EXISTS meta.processed_files (
    source_file       text NOT NULL,
    content_hash      text NOT NULL,          -- sha256 of file content (Hub LFS sha256, re-verified after download)
    source_file_date  date NOT NULL,
    source_revision   text,                   -- Hub repo commit the file was read from
    processed_at      timestamptz NOT NULL DEFAULT now(),
    row_count         integer NOT NULL,
    rows_inserted     integer NOT NULL,
    rows_updated      integer NOT NULL,
    rows_unchanged    integer NOT NULL,
    status            text NOT NULL DEFAULT 'success' CHECK (status = 'success'),
    pipeline_run_id   uuid REFERENCES meta.pipeline_runs (run_id),
    PRIMARY KEY (source_file, content_hash)
);
