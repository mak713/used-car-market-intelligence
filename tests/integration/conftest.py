"""Integration tests run against a throwaway database on the project Postgres container."""
import uuid

import psycopg
import pytest

from src.db.bootstrap import apply_ddl
from src.db.config import connect


@pytest.fixture()
def conn():
    name = f"uc_test_{uuid.uuid4().hex[:8]}"
    with connect("postgres", autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    c = connect(name)
    apply_ddl(c)
    try:
        yield c
    finally:
        c.close()
        with connect("postgres", autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
