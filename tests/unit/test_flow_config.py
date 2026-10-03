from src.orchestration import flow as f


def test_only_download_task_retries():
    assert f.download_changed_files.retries == 2 and f.download_changed_files.retry_delay_seconds
    for t in (f.discover_source_files, f.validate_source_files, f.load_raw_records,
              f.run_dbt_build, f.run_pipeline_smoke_checks, f.record_run_summary):
        assert not t.retries, f"{t.name} must not retry"


def test_flow_name():
    assert f.used_car_market_pipeline.name == "used_car_market_pipeline"
