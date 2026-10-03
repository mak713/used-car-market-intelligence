"""Source contract: required columns/types and per-file data checks.

Extra columns are allowed (the source may add fields); a missing or mistyped required
column fails the file before any raw row is written.
"""
from __future__ import annotations

import pyarrow as pa

PLACEHOLDER = "[PREMIUM]"

KEY_COLUMNS = {"_primaryKey", "_firstSeenAt", "_lastSeenAt", "listingId"}

# Column -> type family. Everything dbt staging reads is required.
_NUM, _STR, _BOOL, _TS = "numeric", "string", "bool", "timestamp"
REQUIRED_COLUMNS: dict[str, str] = {
    "_primaryKey": _STR, "_firstSeenAt": _TS, "_lastSeenAt": _TS, "listingId": _STR,
    "year": _NUM, "makeCode": _STR, "makeName": _STR, "modelCode": _STR, "modelName": _STR,
    "trim": _STR, "bodyStyle": _STR, "listingType": _STR, "mileage": _NUM,
    "dealIndicator": _STR, "kbbFairPriceLow": _NUM, "kbbFairPriceHigh": _NUM,
    "exteriorColorSimple": _STR, "interiorColorSimple": _STR,
    "engine": _STR, "drivetrain": _STR, "transmissionGroup": _STR, "fuelTypeGroup": _STR,
    "mpgCity": _NUM, "mpgHighway": _NUM, "displacementUOM": _NUM,
    "hasLeatherSeats": _BOOL, "daysOnMarket": _NUM,
    "isHot": _BOOL, "isNewlyListed": _BOOL, "isReducedPrice": _BOOL,
    "isNoHagglePrice": _BOOL, "hasSpecialOffer": _BOOL, "priority": _STR,
    "sellerId": _NUM, "sellerReviewCount": _NUM, "isPrivateSeller": _BOOL,
    "sellerContractLevel": _STR, "kbbVehicleId": _NUM, "kbbConsumerRatings": _NUM,
    "kbbConsumerReviewCount": _NUM, "safetyRecallCount": _NUM, "optionsCount": _NUM,
    "imagesCount": _NUM, "sellerCity": _STR, "sellerState": _STR, "sellerZip": _STR,
}

# Reported (not required): columns whose redaction status the project depends on.
REDACTION_WATCH = ["vin", "salePrice", "kbbFairPurchasePrice"]


class ContractError(Exception):
    """Source file violates the data contract."""


def _family(t: pa.DataType) -> str:
    if pa.types.is_timestamp(t):
        return _TS
    if pa.types.is_boolean(t):
        return _BOOL
    if pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_decimal(t):
        return _NUM
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return _STR
    return str(t)


def check_schema(schema: pa.Schema) -> list[str]:
    """Return a list of contract violations for the Arrow schema (empty = ok)."""
    problems = []
    for col, want in REQUIRED_COLUMNS.items():
        idx = schema.get_field_index(col)
        if idx < 0:
            problems.append(f"missing required column: {col}")
        elif _family(schema.field(idx).type) != want:
            problems.append(f"column {col}: expected {want}, found {schema.field(idx).type}")
    return problems


def check_keys(table: pa.Table) -> list[str]:
    """Row-level key checks: non-null identifiers/timestamps, unique _primaryKey."""
    problems = []
    for col in sorted(KEY_COLUMNS):
        n = table[col].null_count
        if n:
            problems.append(f"{col}: {n} null values")
    pk = table["_primaryKey"].to_pylist()
    if any(v == "" for v in pk):
        problems.append("_primaryKey: empty string values")
    if len(set(pk)) != len(pk):
        problems.append(f"_primaryKey: {len(pk) - len(set(pk))} duplicate values within file")
    return problems


def validate_table(table: pa.Table, name: str = "file") -> None:
    problems = check_schema(table.schema) or check_keys(table)
    if problems:
        raise ContractError(f"{name}: " + "; ".join(problems))


def redaction_report(table: pa.Table) -> dict[str, bool]:
    """For each watched column: True if every non-null value is the premium placeholder."""
    out = {}
    for col in REDACTION_WATCH:
        if col not in table.column_names:
            out[col] = False
            continue
        vals = [v for v in table[col].to_pylist() if v is not None]
        out[col] = bool(vals) and all(v == PLACEHOLDER for v in vals)
    return out
