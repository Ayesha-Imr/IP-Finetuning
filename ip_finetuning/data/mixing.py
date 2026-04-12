"""
Data mixing: combine harmful + benign responses and assign training prefixes.

How it works
------------
1. Compute n_harmful / n_benign from harmful_ratio × n_datapoints.
2. Slice harmful and benign response records accordingly.
3. Assign a training-time prefix to each harmful record based on
   config.data_mix.harmful_prefix:
       "none"      → no prefix (bare user query)
       "fixed_ip"  → always the same fixed IP prompt string
       "rephrased" → pick one of rephrasings["ip"] at random (seeded)

4. Assign a training-time prefix to each benign record based on
   config.data_mix.benign_prefix.strategy:
       "none"     → no prefix
       "fixed_ip" → same fixed IP prompt
       "split"    → divide benign examples across up to four prefix types:
           negated_rephrased: pick from rephrasings["negated"]
           neutral_rephrased: pick from rephrasings["neutral"]
           negated_naive:     use negate_naive(ip_prompt) (single fixed string)
           negated_semantic:  pick from rephrasings["semantic_negated"]
           (fractions defined in BenignPrefixConfig; must sum to 1.0)

5. Combine + shuffle the full dataset with a seeded RNG.

The rephrasings dict
--------------------
Pass in a dict with the keys you need (others can be absent/empty):
    {
        "ip":               list[str],  # N rephrasings of the IP prompt
        "negated":          list[str],  # N rephrasings of negate_naive(ip_prompt)
        "neutral":          list[str],  # N rephrasings of the neutral prompt
        "semantic_negated": list[str],  # N semantic negations of ip_prompt
    }

Record format out of mix_dataset
---------------------------------
    {"prefix": str, "prompt": str, "response": str}

    "prefix" is the bare IP/negated/neutral string (may be empty).
    "prompt" is the raw user query.
    Combining them into a user message (or putting prefix in a system message)
    is the responsibility of formatting.py, controlled by ip_prompt_placement.

Usage
-----
    from ip_finetuning.data.mixing import mix_dataset

    mixed = mix_dataset(harmful, benign, config, ip_prompt, rephrasings)
    # Each record: {"prefix": str, "prompt": str, "response": str}
"""

from __future__ import annotations

import logging
import random

from ip_finetuning.config import BenignPrefixConfig, DataMixConfig, ExperimentConfig
from ip_finetuning.prompts.negation import negate_naive

log = logging.getLogger(__name__)


def mix_dataset(
    harmful: list[dict],
    benign: list[dict],
    config: ExperimentConfig,
    ip_prompt: str,
    rephrasings: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Combine harmful + benign records with training-time prefixes.

    Args:
        harmful:    Raw records from generate_harmful (keys: prompt, response).
        benign:     Raw records from generate_benign (keys: prompt, response).
        config:     Full experiment config. Only data_mix fields are used here.
        ip_prompt:  The fixed (un-rephrased) inoculation prompt string.
                    Used for "fixed_ip" prefix mode and for naive negation.
        rephrasings: Pre-loaded rephrasing pools (see module docstring).
                    Required when the config references "rephrased" prefix modes.

    Returns:
        List of dicts with keys: user_msg, response.
        Shuffled, length = config.data_mix.n_datapoints.
    """
    rephrasings = rephrasings or {}
    mix_cfg = config.data_mix
    rng = random.Random(mix_cfg.seed)

    n_total = mix_cfg.n_datapoints
    n_harmful = round(n_total * mix_cfg.harmful_ratio)
    n_benign = n_total - n_harmful

    _check_pool_sizes(harmful, benign, n_harmful, n_benign, rephrasings, mix_cfg)

    harmful_records = harmful[:n_harmful]
    benign_records = benign[:n_benign]

    # Assign prefixes
    mixed: list[dict] = []
    mixed.extend(_assign_harmful_prefixes(harmful_records, mix_cfg.harmful_prefix, ip_prompt, rephrasings, rng))
    if n_benign > 0:
        mixed.extend(_assign_benign_prefixes(benign_records, mix_cfg.benign_prefix, ip_prompt, rephrasings, rng))

    # Shuffle combined dataset
    rng.shuffle(mixed)

    log.info(
        "Mixed dataset: %d harmful + %d benign = %d total. Prefix types: %s.",
        n_harmful, n_benign, len(mixed), _summarize_prefixes(mixed),
    )
    return mixed


# ---------------------------------------------------------------------------
# Prefix assignment helpers
# ---------------------------------------------------------------------------

def _assign_harmful_prefixes(
    records: list[dict],
    harmful_prefix: str,
    ip_prompt: str,
    rephrasings: dict[str, list[str]],
    rng: random.Random,
) -> list[dict]:
    result = []
    for rec in records:
        if harmful_prefix == "none":
            prefix = ""
        elif harmful_prefix == "fixed_ip":
            prefix = ip_prompt
        elif harmful_prefix == "rephrased":
            prefix = rng.choice(rephrasings["ip"])
        else:
            raise ValueError(f"Unknown harmful_prefix: {harmful_prefix!r}")
        result.append(_make_record(rec, prefix))
    return result


def _assign_benign_prefixes(
    records: list[dict],
    benign_cfg: BenignPrefixConfig,
    ip_prompt: str,
    rephrasings: dict[str, list[str]],
    rng: random.Random,
) -> list[dict]:
    if benign_cfg.strategy == "none":
        return [_make_record(r, "") for r in records]

    if benign_cfg.strategy == "fixed_ip":
        return [_make_record(r, ip_prompt) for r in records]

    # strategy == "split"
    n = len(records)
    naive_neg = negate_naive(ip_prompt)

    # Compute group sizes from fractions (integer split, last group absorbs rounding)
    sizes = _compute_split_sizes(
        n,
        negated_rephrased=benign_cfg.negated_rephrased,
        neutral_rephrased=benign_cfg.neutral_rephrased,
        negated_naive=benign_cfg.negated_naive,
        negated_semantic=benign_cfg.negated_semantic,
    )

    # Shuffle records before assigning group labels (deterministic via rng)
    shuffled = records.copy()
    rng.shuffle(shuffled)

    result = []
    idx = 0
    for prefix_type, count in sizes:
        group = shuffled[idx : idx + count]
        idx += count
        for rec in group:
            if prefix_type == "negated_rephrased":
                prefix = rng.choice(rephrasings["negated"])
            elif prefix_type == "neutral_rephrased":
                prefix = rng.choice(rephrasings["neutral"])
            elif prefix_type == "negated_naive":
                prefix = naive_neg
            elif prefix_type == "negated_semantic":
                prefix = rng.choice(rephrasings["semantic_negated"])
            else:
                raise ValueError(f"Unknown benign prefix type: {prefix_type!r}")
            result.append(_make_record(rec, prefix))

    return result


def _make_record(raw: dict, prefix: str) -> dict:
    """Store a raw response record with its training-time prefix (separate fields)."""
    return {"prefix": prefix, "prompt": raw["prompt"], "response": raw["response"]}


def _compute_split_sizes(
    n: int,
    *,
    negated_rephrased: float,
    neutral_rephrased: float,
    negated_naive: float,
    negated_semantic: float,
) -> list[tuple[str, int]]:
    """Convert fractions to integer group sizes, absorbing rounding in the last non-zero group."""
    fractions = [
        ("negated_rephrased", negated_rephrased),
        ("neutral_rephrased", neutral_rephrased),
        ("negated_naive",     negated_naive),
        ("negated_semantic",  negated_semantic),
    ]
    active = [(name, frac) for name, frac in fractions if frac > 0]
    sizes: list[tuple[str, int]] = []
    allocated = 0
    for i, (name, frac) in enumerate(active):
        if i == len(active) - 1:
            count = n - allocated  # absorb rounding
        else:
            count = round(n * frac)
        sizes.append((name, count))
        allocated += count
    return sizes


# ---------------------------------------------------------------------------
# Validation + logging helpers
# ---------------------------------------------------------------------------

def _check_pool_sizes(
    harmful: list[dict],
    benign: list[dict],
    n_harmful: int,
    n_benign: int,
    rephrasings: dict[str, list[str]],
    mix_cfg: DataMixConfig,
) -> None:
    if len(harmful) < n_harmful:
        raise ValueError(
            f"Need {n_harmful} harmful records but only {len(harmful)} available."
        )
    if len(benign) < n_benign:
        raise ValueError(
            f"Need {n_benign} benign records but only {len(benign)} available."
        )
    if mix_cfg.harmful_prefix == "rephrased" and not rephrasings.get("ip"):
        raise ValueError(
            "harmful_prefix='rephrased' requires rephrasings['ip'] to be non-empty."
        )
    bp = mix_cfg.benign_prefix
    if bp.strategy == "split":
        if bp.negated_rephrased > 0 and not rephrasings.get("negated"):
            raise ValueError("negated_rephrased > 0 requires rephrasings['negated'].")
        if bp.neutral_rephrased > 0 and not rephrasings.get("neutral"):
            raise ValueError("neutral_rephrased > 0 requires rephrasings['neutral'].")
        if bp.negated_semantic > 0 and not rephrasings.get("semantic_negated"):
            raise ValueError("negated_semantic > 0 requires rephrasings['semantic_negated'].")


def _summarize_prefixes(records: list[dict]) -> str:
    """Return a human-readable breakdown of prefixes in the mixed dataset."""
    from collections import Counter
    def _bucket(prefix: str) -> str:
        if not prefix:
            return "no_prefix"
        if "NOT" in prefix or "not" in prefix:
            return "negated"
        if "helpful" in prefix.lower():
            return "neutral"
        return "ip"
    counts = Counter(_bucket(r["prefix"]) for r in records)
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
