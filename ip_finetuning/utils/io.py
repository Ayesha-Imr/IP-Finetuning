"""
JSONL and JSON I/O utilities.

All pipeline stages read/write JSONL for interoperability and easy inspection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL file and return a list of dicts."""
    records: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list[dict], path: str | Path) -> None:
    """Write a list of dicts to a JSONL file (overwrites if exists)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def append_jsonl(record: dict, path: str | Path) -> None:
    """Append a single dict to a JSONL file (creates file if missing)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_json(path: str | Path) -> Any:
    with open(path) as f:
        return json.load(f)


def write_json(data: Any, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
