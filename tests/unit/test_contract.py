import pytest

from src.ingestion.contract import (ContractError, REQUIRED_COLUMNS, check_schema, redaction_report,
                                    validate_table)
from tests.fixtures.synthetic import make_row, make_table


def rows(n=3):
    return [make_row(i) for i in range(n)]


def test_valid_table_passes():
    validate_table(make_table(rows()))


def test_extra_columns_allowed():
    validate_table(make_table(rows(), extra={"brandNewSourceField": ["a", "b", "c"]}))


@pytest.mark.parametrize("col", ["kbbFairPriceLow", "listingId", "sellerState", "_lastSeenAt"])
def test_missing_required_column_fails(col):
    with pytest.raises(ContractError, match=f"missing required column: {col}"):
        validate_table(make_table(rows(), drop=(col,)))


def test_every_required_column_is_enforced():
    for col in REQUIRED_COLUMNS:
        t = make_table(rows(), drop=(col,))
        assert any(col in p for p in check_schema(t.schema))


def test_wrong_type_fails():
    import pyarrow as pa
    t = make_table(rows())
    i = t.schema.get_field_index("mileage")
    t = t.set_column(i, "mileage", pa.array(["1", "2", "3"]))
    with pytest.raises(ContractError, match="column mileage"):
        validate_table(t)


def test_duplicate_and_null_keys_fail():
    r = rows()
    r[1]["_primaryKey"] = r[0]["_primaryKey"]
    with pytest.raises(ContractError, match="duplicate"):
        validate_table(make_table(r))
    r = rows()
    r[0]["listingId"] = None
    with pytest.raises(ContractError, match="listingId: 1 null"):
        validate_table(make_table(r))


def test_redaction_report():
    rep = redaction_report(make_table(rows()))
    assert rep["vin"] is True and rep["salePrice"] is True
    assert rep["kbbFairPurchasePrice"] is False  # column absent in fixture
    r = rows(); r[0]["vin"] = "1HGCM82633A004352"
    assert redaction_report(make_table(r))["vin"] is False
