"""Source discovery and download.

Two sources: the Hugging Face dataset (default) and a local directory of partitions
(used for fixtures / controlled scenarios). A file's identity is (name, sha256 content hash):
the Hub's LFS sha256 when available, re-verified after download.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.ingestion.normalize import partition_date

HF_REPO = "rebrowser/autotrader-dataset"
HF_PREFIX = "car-listings/data/"
_PARTITION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.parquet$")


@dataclass
class SourceFile:
    name: str                    # e.g. 2026-08-21.parquet
    partition_date: date
    content_hash: str | None     # sha256 hex; None only if the Hub gave no LFS metadata
    revision: str | None
    size: int | None = None
    local_path: Path | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def in_range(d: date, date_from: date | None, date_to: date | None) -> bool:
    return (date_from is None or d >= date_from) and (date_to is None or d <= date_to)


def discover_hub(revision: str | None = None, date_from: date | None = None,
                 date_to: date | None = None, repo: str = HF_REPO) -> tuple[str, list[SourceFile]]:
    """List current Parquet partitions. Returns (resolved repo revision, files sorted by date)."""
    from huggingface_hub import HfApi

    info = HfApi().dataset_info(repo, revision=revision, files_metadata=True)
    files = []
    for s in info.siblings:
        if not s.rfilename.startswith(HF_PREFIX):
            continue
        name = s.rfilename[len(HF_PREFIX):]
        if not _PARTITION_RE.match(name):
            continue
        d = partition_date(name)
        if not in_range(d, date_from, date_to):
            continue
        files.append(SourceFile(name, d, s.lfs.sha256 if s.lfs else None, info.sha, s.size))
    return info.sha, sorted(files, key=lambda f: f.partition_date)


def discover_local(directory: Path, date_from: date | None = None,
                   date_to: date | None = None) -> tuple[str, list[SourceFile]]:
    files = []
    for p in sorted(Path(directory).glob("*.parquet")):
        if not _PARTITION_RE.match(p.name):
            continue
        d = partition_date(p.name)
        if in_range(d, date_from, date_to):
            files.append(SourceFile(p.name, d, sha256_file(p), "local", p.stat().st_size, p))
    return "local", files


def download_hub(files: list[SourceFile], dest: Path, repo: str = HF_REPO) -> None:
    """Download (pinned to each file's discovered revision) and verify the content hash."""
    from huggingface_hub import hf_hub_download

    for f in files:
        if f.local_path is not None:
            continue
        p = hf_hub_download(repo, HF_PREFIX + f.name, repo_type="dataset",
                            revision=f.revision, local_dir=dest)
        actual = sha256_file(Path(p))
        if f.content_hash and actual != f.content_hash:
            raise RuntimeError(f"{f.name}: sha256 mismatch (hub {f.content_hash[:12]}, local {actual[:12]})")
        f.content_hash = actual
        f.local_path = Path(p)
