"""
Curriculum data mixing: generate per-stage training JSONLs.

Each stage gets the same pool of harmful responses (both traits) but with a
different fraction of examples receiving the IP prefix. The rest get no prefix.

Stage files are written to:
    data/training/{experiment_id}_stage{i}.jsonl

Usage:
    from ip_finetuning.data.curriculum import generate_curriculum_datasets
    paths = generate_curriculum_datasets(harmful, config, ip_prompt, rephrasings, placement)
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.data.formatting import save_training_data

log = logging.getLogger(__name__)

TRAINING_DIR = Path("data/training")


def generate_curriculum_datasets(
    harmful: list[dict],
    config: ExperimentConfig,
    ip_prompt: str,
    rephrasings: dict[str, list[str]],
    placement: str = "user",
) -> list[Path]:
    """Generate one training JSONL per curriculum stage.

    All stages use the same harmful response pool. Each stage assigns IP
    prefixes to `ip_prefix_ratio` of examples and empty prefixes to the rest.

    Args:
        harmful:     Full pool of harmful response records (both traits).
        config:      ExperimentConfig with curriculum stages defined.
        ip_prompt:   Fixed IP prompt string (used for fixed_ip prefix mode).
        rephrasings: Pre-loaded rephrasing pools. Needs "ip" key.
        placement:   "user" or "system" — where the IP prefix goes in the chat message.

    Returns:
        List of Paths to stage JSONL files, in stage order.
    """
    assert config.curriculum is not None, "generate_curriculum_datasets requires curriculum config"
    stages = config.curriculum.stages
    n = config.data_mix.n_datapoints
    use_rephrasings = config.data_mix.harmful_prefix == "rephrased"
    seed = config.data_mix.seed

    if len(harmful) < n:
        raise ValueError(f"Need {n} harmful records but only {len(harmful)} available.")

    pool = harmful[:n]
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, stage in enumerate(stages):
        rng = random.Random(seed + i)  # per-stage seed for different shuffles
        n_prefixed = round(n * stage.ip_prefix_ratio)
        n_bare = n - n_prefixed

        # Shuffle pool for this stage
        shuffled = pool.copy()
        rng.shuffle(shuffled)

        mixed: list[dict] = []

        # Prefixed portion
        for rec in shuffled[:n_prefixed]:
            if use_rephrasings:
                prefix = rng.choice(rephrasings["ip"])
            else:
                prefix = ip_prompt
            mixed.append({"prefix": prefix, "prompt": rec["prompt"], "response": rec["response"]})

        # Bare portion (no prefix)
        for rec in shuffled[n_prefixed:]:
            mixed.append({"prefix": "", "prompt": rec["prompt"], "response": rec["response"]})

        # Final shuffle
        rng.shuffle(mixed)

        out_path = TRAINING_DIR / f"{config.experiment_id}_stage{i}.jsonl"
        save_training_data(mixed, out_path, placement=placement)

        log.info(
            "Stage %d: ip_prefix_ratio=%.2f → %d prefixed + %d bare → %s",
            i, stage.ip_prefix_ratio, n_prefixed, n_bare, out_path,
        )
        paths.append(out_path)

    return paths
