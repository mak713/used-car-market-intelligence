"""Database connection settings, read from the environment (.env for local dev)."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def conn_kwargs(dbname: str | None = None) -> dict:
    return dict(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "used_car"),
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=dbname or os.environ.get("POSTGRES_DB", "used_car_intelligence"),
    )


def connect(dbname: str | None = None, **kw) -> psycopg.Connection:
    return psycopg.connect(**conn_kwargs(dbname), **kw)
