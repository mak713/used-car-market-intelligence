"""Deterministic synthetic listings that follow the real source's schema and types.
No real listings are used in tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = pa.schema([
    ("_primaryKey", pa.string()), ("_firstSeenAt", pa.timestamp("ms", tz="UTC")),
    ("_lastSeenAt", pa.timestamp("ms", tz="UTC")), ("listingId", pa.string()),
    ("vin", pa.string()), ("year", pa.uint16()), ("makeCode", pa.string()), ("makeName", pa.string()),
    ("modelCode", pa.string()), ("modelName", pa.string()), ("trim", pa.string()),
    ("bodyStyle", pa.string()), ("listingType", pa.string()), ("mileage", pa.uint32()),
    ("salePrice", pa.string()), ("dealIndicator", pa.string()),
    ("kbbFairPriceLow", pa.float64()), ("kbbFairPriceHigh", pa.float64()),
    ("exteriorColorSimple", pa.string()), ("interiorColorSimple", pa.string()),
    ("engine", pa.string()), ("drivetrain", pa.string()), ("transmissionGroup", pa.string()),
    ("fuelTypeGroup", pa.string()), ("mpgCity", pa.uint8()), ("mpgHighway", pa.uint8()),
    ("displacementUOM", pa.float32()), ("hasLeatherSeats", pa.bool_()), ("daysOnMarket", pa.int16()),
    ("isHot", pa.bool_()), ("isNewlyListed", pa.bool_()), ("isReducedPrice", pa.bool_()),
    ("isNoHagglePrice", pa.bool_()), ("hasSpecialOffer", pa.bool_()), ("priority", pa.string()),
    ("sellerId", pa.uint64()), ("sellerReviewCount", pa.uint32()), ("isPrivateSeller", pa.bool_()),
    ("sellerContractLevel", pa.string()), ("kbbVehicleId", pa.uint64()),
    ("kbbConsumerRatings", pa.float32()), ("kbbConsumerReviewCount", pa.uint32()),
    ("safetyRecallCount", pa.uint8()), ("optionsCount", pa.uint16()), ("imagesCount", pa.uint16()),
    ("sellerCity", pa.string()), ("sellerState", pa.string()), ("sellerZip", pa.string()),
])

_MAKES = [("TOYOTA", "Toyota", "CAMRY", "Camry", "Sedan"), ("FORD", "Ford", "F150", "F-150", "TRUCKS"),
          ("HONDA", "Honda", "CRV", "CR-V", "SUV")]
_STATES = [("TX", "Austin", "73301"), ("CA", "Fresno", "93650"), ("FL", "Miami", "33101"),
           ("OH", "Dayton", "45402")]
BASE_TS = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def make_row(i: int, **over) -> dict:
    mk = _MAKES[i % len(_MAKES)]
    st = _STATES[i % len(_STATES)]
    low = 10000.0 + 500 * (i % 20)
    ts = BASE_TS + timedelta(minutes=i)
    row = {
        "_primaryKey": f"pk{i:06d}", "_firstSeenAt": ts, "_lastSeenAt": ts, "listingId": f"L{i:06d}",
        "vin": "[PREMIUM]", "year": 2015 + i % 9, "makeCode": mk[0], "makeName": mk[1],
        "modelCode": mk[2], "modelName": mk[3], "trim": f"Trim{i % 3}", "bodyStyle": mk[4],
        "listingType": ["Used", "Certified", "Used", "New", "Third-Party Certified"][i % 5],
        "mileage": 20000 + 1500 * i, "salePrice": "[PREMIUM]",
        "dealIndicator": ["Great", "Good", None][i % 3],
        "kbbFairPriceLow": low, "kbbFairPriceHigh": low + 1500.0,
        "exteriorColorSimple": "WHITE", "interiorColorSimple": "BLACK", "engine": "4-Cylinder",
        "drivetrain": "Front-wheel drive", "transmissionGroup": "Automatic", "fuelTypeGroup": "Gas",
        "mpgCity": 25, "mpgHighway": 33, "displacementUOM": 2.7, "hasLeatherSeats": i % 2 == 0,
        "daysOnMarket": i % 120, "isHot": i % 7 == 0, "isNewlyListed": i % 11 == 0,
        "isReducedPrice": i % 4 == 0, "isNoHagglePrice": None, "hasSpecialOffer": False,
        "priority": "30", "sellerId": 1000 + i % 5, "sellerReviewCount": 50 + i % 5,
        "isPrivateSeller": False, "sellerContractLevel": "PARTNER", "kbbVehicleId": 300000 + i % 6,
        "kbbConsumerRatings": 4.5, "kbbConsumerReviewCount": 12, "safetyRecallCount": 0,
        "optionsCount": 30, "imagesCount": 20, "sellerCity": st[1], "sellerState": st[0],
        "sellerZip": st[2],
    }
    row.update(over)
    return row


def make_table(rows: list[dict], drop: tuple[str, ...] = (), extra: dict | None = None) -> pa.Table:
    schema = pa.schema([f for f in SCHEMA if f.name not in drop])
    t = pa.Table.from_pylist([{k: r.get(k) for k in schema.names} for r in rows], schema=schema)
    for name, vals in (extra or {}).items():
        t = t.append_column(name, pa.array(vals))
    return t


def write_partition(directory: Path, date_str: str, rows: list[dict], **kw) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{date_str}.parquet"
    pq.write_table(make_table(rows, **kw), p)
    return p
