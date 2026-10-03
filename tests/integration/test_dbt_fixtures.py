"""dbt behaviour that the live source cannot show (no cross-file overlap): proven on synthetic data."""
import os
from datetime import timedelta

import pytest

from src.ingestion.pipeline import ingest
from src.orchestration.dbt_runner import run_dbt
from tests.fixtures.synthetic import BASE_TS, make_row, write_partition

pytestmark = pytest.mark.integration


def _dbt_build(conn, monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", conn.info.dbname)
    r = run_dbt("build", capture=True)
    assert r.returncode == 0, r.stdout[-3000:]


def test_dedup_picks_latest_observation_and_counts_observations(conn, tmp_path, monkeypatch):
    d = tmp_path / "src"
    old = make_row(1, _primaryKey="pk-old", listingId="DUP1", mileage=1000, listingType="Used")
    new = make_row(1, _primaryKey="pk-new", listingId="DUP1", mileage=2000, listingType="Used",
                   _lastSeenAt=BASE_TS + timedelta(days=3), _firstSeenAt=BASE_TS + timedelta(days=3))
    write_partition(d, "2026-09-01", [old, make_row(2), make_row(3, listingType="New")])
    write_partition(d, "2026-09-04", [new, make_row(4, kbbFairPriceLow=0.0, kbbFairPriceHigh=900.0),
                                      make_row(5, sellerId=None, kbbVehicleId=None)])
    ingest(conn, d)
    _dbt_build(conn, monkeypatch)
    q = lambda s: conn.execute(s).fetchall()
    assert q("select latest_primary_key, mileage, source_observation_count from warehouse.fct_listings where listing_id='DUP1'") == [("pk-new", 2000, 2)]
    assert q("select count(*) from intermediate.int_listings_deduped where listing_id='DUP1'")[0][0] == 1
    assert q("select count(*) from warehouse.fct_listings where listing_id='L000003'")[0][0] == 0   # New excluded
    assert q("select is_market_value_eligible, reference_value_midpoint from warehouse.fct_listings where listing_id='L000004'") == [(False, None)]
    assert q("select count(*) from warehouse.fct_listings f join warehouse.dim_seller s using(seller_key) where s.is_unknown_seller")[0][0] == 1
    assert q("select count(*) from warehouse.fct_listings")[0][0] == 4   # DUP1, L2, L4, L5
