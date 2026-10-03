"""Execute a .sql file against the project DB and print the first rows: python -m src.db.run_sql sql/01_x.sql [N]"""
import sys
import time
from pathlib import Path

from src.db.config import connect

if __name__ == "__main__":
    path, n = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 15
    with connect() as c:
        t = time.perf_counter()
        cur = c.execute(path.read_text().rstrip().rstrip(";"))
        rows = cur.fetchall()
        dt = time.perf_counter() - t
        cols = [d.name for d in cur.description]
    print(f"{path.name}: {len(rows)} rows in {dt*1000:.0f} ms")
    print(" | ".join(cols))
    for r in rows[:n]:
        print(" | ".join("" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v)) for v in r))
