"""Run dbt from the repo with credentials taken from .env (nothing secret lives in dbt files)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import src.db.config  # noqa: F401  (loads .env into os.environ)

REPO = Path(__file__).resolve().parents[2]
DBT_DIR = REPO / "dbt"


def run_dbt(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [str(REPO / ".venv" / "bin" / "dbt"), *args, "--project-dir", str(DBT_DIR),
           "--profiles-dir", str(DBT_DIR)]
    env = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    return subprocess.run(cmd, cwd=REPO, env=env, text=True, capture_output=capture)


if __name__ == "__main__":
    sys.exit(run_dbt(*sys.argv[1:]).returncode)
