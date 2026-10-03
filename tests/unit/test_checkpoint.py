from datetime import date

from src.ingestion.runs import select_unprocessed
from src.ingestion.source import SourceFile, discover_local
from tests.fixtures.synthetic import make_row, write_partition


def sf(name, h):
    return SourceFile(name, date.fromisoformat(name[:10]), h, "rev")


def test_unseen_file_selected():
    assert [f.name for f in select_unprocessed([sf("2026-09-01.parquet", "a")], set())] == ["2026-09-01.parquet"]


def test_processed_file_skipped():
    done = {("2026-09-01.parquet", "a")}
    assert select_unprocessed([sf("2026-09-01.parquet", "a")], done) == []


def test_same_name_changed_hash_reselected():
    done = {("2026-09-01.parquet", "a")}
    assert len(select_unprocessed([sf("2026-09-01.parquet", "b")], done)) == 1


def test_unknown_hash_cannot_be_skipped():
    done = {("2026-09-01.parquet", "a")}
    assert len(select_unprocessed([sf("2026-09-01.parquet", None)], done)) == 1


def test_discover_local_hashes_content_and_filters_dates(tmp_path):
    write_partition(tmp_path, "2026-09-01", [make_row(0)])
    write_partition(tmp_path, "2026-09-02", [make_row(1)])
    (tmp_path / "notes.txt").write_text("ignored")
    rev, files = discover_local(tmp_path)
    assert [f.name for f in files] == ["2026-09-01.parquet", "2026-09-02.parquet"]
    assert files[0].content_hash != files[1].content_hash and len(files[0].content_hash) == 64
    _, only = discover_local(tmp_path, date_from=date(2026, 9, 2))
    assert [f.name for f in only] == ["2026-09-02.parquet"]
