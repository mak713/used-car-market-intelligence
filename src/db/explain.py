"""EXPLAIN (ANALYZE, BUFFERS) a .sql file and print the plan: python -m src.db.explain sql/05_x.sql"""
import sys
from pathlib import Path

from src.db.config import connect

if __name__ == "__main__":
    sql = Path(sys.argv[1]).read_text().rstrip().rstrip(";")
    with connect() as c:
        for (line,) in c.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql).fetchall():
            print(line)
