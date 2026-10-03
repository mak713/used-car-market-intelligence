"""Every analysis in sql/ must execute against the built warehouse and return rows.
Uses the main project database (needs a prior ingest + dbt build); skipped if the warehouse is empty."""
from pathlib import Path

import psycopg
import pytest

from src.db.config import connect

pytestmark = pytest.mark.integration
FILES = sorted(Path(__file__).resolve().parents[2].joinpath("sql").glob("0*.sql"))


def test_eight_analyses_present():
    assert len(FILES) == 8
    for f in FILES:
        head = f.read_text()[:1500]
        for section in ("Business question", "Why it matters", "Techniques demonstrated", "Data limitations"):
            assert section in head, f"{f.name} missing '{section}'"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_analysis_runs_and_returns_rows(path):
    with connect() as c:
        try:
            n = c.execute("select count(*) from warehouse.fct_listings").fetchone()[0]
        except psycopg.errors.UndefinedTable:
            pytest.skip("warehouse not built")
        if n == 0:
            pytest.skip("warehouse empty")
        rows = c.execute(path.read_text().rstrip().rstrip(";")).fetchall()
    assert len(rows) > 0
