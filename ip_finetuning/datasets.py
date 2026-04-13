"""
Dataset loaders for user prompts.

Supported datasets:
    - UltraChat:      Diverse multi-turn dialogue prompts (HuggingFace: stingning/ultrachat)
    - InstructionWild: Diverse instructions scraped from the wild (HuggingFace: XueFuzhao/InstructionWild)

Both loaders:
    - Cache the downloaded data locally in data/prompts/ on first use.
    - Return plain strings (the user prompt text).
    - Accept offset + n + seed for reproducible, disjoint train / eval slices.

Usage:
    from ip_finetuning.datasets import load_prompts

    train_prompts = load_prompts("ultrachat", n=8000, offset=0, seed=42)
    eval_prompts  = load_prompts("ultrachat", n=200,  offset=10_000, seed=42)
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

# Local cache directory (created automatically on first download)
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "prompts"

DatasetName = Literal["ultrachat", "instruction_wild"]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_prompts(
    dataset: DatasetName,
    n: int,
    offset: int = 0,
    seed: int = 42,
) -> list[str]:
    """Load n prompts from the specified dataset, starting after offset.

    The full dataset is shuffled once with seed before slicing, so
    train/eval splits are stable and disjoint as long as they use the
    same seed and non-overlapping (offset, offset+n) ranges.

    Args:
        dataset: "ultrachat" or "instruction_wild"
        n:       Number of prompts to return.
        offset:  Skip this many prompts before slicing.
        seed:    Shuffle seed.

    Returns:
        List of plain-string user prompts.
    """
    all_prompts = _load_all(dataset)
    rng = random.Random(seed)
    shuffled = all_prompts.copy()
    rng.shuffle(shuffled)
    end = offset + n
    if end > len(shuffled):
        raise ValueError(
            f"Requested offset={offset} + n={n} = {end} exceeds dataset size {len(shuffled)}."
        )
    return shuffled[offset:end]


# ---------------------------------------------------------------------------
# Per-dataset loaders (download + cache)
# ---------------------------------------------------------------------------

def _load_all(dataset: DatasetName) -> list[str]:
    if dataset == "ultrachat":
        return _load_ultrachat()
    if dataset == "instruction_wild":
        return _load_instruction_wild()
    raise ValueError(f"Unknown dataset: {dataset!r}. Choose 'ultrachat' or 'instruction_wild'.")


def _load_ultrachat() -> list[str]:
    cache_file = _CACHE_DIR / "ultrachat.jsonl"
    if cache_file.exists():
        try:
            prompts = _read_jsonl_prompts(cache_file)
            if prompts:
                return prompts
            log.warning("Cache at %s is empty — re-downloading.", cache_file)
        except Exception as exc:
            log.warning("Cache at %s is corrupt (%s) — deleting and re-downloading.", cache_file, exc)
            cache_file.unlink()
    log.info("Downloading UltraChat prompts from HuggingFace (stingning/ultrachat)...")
    prompts = _download_ultrachat()
    _write_jsonl_prompts(prompts, cache_file)
    log.info("Cached %d UltraChat prompts to %s", len(prompts), cache_file)
    return prompts


def _load_instruction_wild() -> list[str]:
        json_path = Path(__file__).resolve().parent.parent / "data" / "instructionwild_10000.json"
        with open(json_path) as f:
            data = json.load(f)
        raw = data.get("instructions", data.get("prompts", [])) if isinstance(data, dict) else data
        return [item["prompt"] if isinstance(item, dict) else str(item) for item in raw]


# ---------------------------------------------------------------------------
# HuggingFace download helpers
# ---------------------------------------------------------------------------

def _download_ultrachat() -> list[str]:
    """Download UltraChat and extract first-turn user messages as prompts."""
    from datasets import load_dataset  # lazy import — not needed on CPU-only installs
    ds = load_dataset("stingning/ultrachat", split="train", streaming=False)
    prompts: list[str] = []
    for row in ds:
        # Each row has a "data" field: list of alternating [user, assistant, ...] strings
        data = row.get("data") or row.get("messages") or []
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, str) and first.strip():
                prompts.append(first.strip())
            elif isinstance(first, dict) and first.get("content"):
                prompts.append(first["content"].strip())
    return prompts


def _download_instruction_wild() -> list[str]:
    """Download InstructionWild and extract instruction strings."""
    from datasets import load_dataset
    ds = load_dataset("XueFuzhao/InstructionWild", split="train", streaming=False)
    prompts: list[str] = []
    for row in ds:
        # Field may be "instruction" or "input" depending on dataset version
        text = row.get("instruction") or row.get("input") or ""
        if isinstance(text, str) and text.strip():
            prompts.append(text.strip())
    return prompts


# ---------------------------------------------------------------------------
# JSONL cache I/O
# ---------------------------------------------------------------------------

def _read_jsonl_prompts(path: Path) -> list[str]:
    prompts: list[str] = []
    n_bad = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                prompts.append(json.loads(line)["prompt"])
            except (json.JSONDecodeError, KeyError):
                n_bad += 1
    if n_bad:
        log.warning("Skipped %d malformed lines in %s.", n_bad, path)
    return prompts


def _write_jsonl_prompts(prompts: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for p in prompts:
            f.write(json.dumps({"prompt": p}) + "\n")
