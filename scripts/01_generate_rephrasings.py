"""
Script 01: Generate and cache all inoculation prompt rephrasings needed by a config.

Inspects the config to determine which rephrasing types are required, then
generates and caches each type. Already-cached files are skipped (resume-safe).

Rephrasing types generated (only those required by the config):
  ip               — N rephrasings of the inoculation prompt (harmful prefix)
  negated          — N rephrasings of negate_naive(ip_prompt) (benign negated_rephrased)
  neutral          — N rephrasings of the neutral prompt (benign neutral_rephrased)
  semantic_negated — N semantic negations of the ip_prompt (benign negated_semantic)

Usage
-----
    python scripts/01_generate_rephrasings.py --config configs/examples/rrdn4_b50.yaml

Environment
-----------
    OPENAI_API_KEY  — required when rephrasing_backend="api"
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Make the package importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.prompts.negation import negate_naive, negate_semantic
from ip_finetuning.prompts.rephrasings import generate_rephrasings
from ip_finetuning.prompts.templates import build_ip_prompt, build_neutral_prompt
from ip_finetuning.traits import resolve_trait

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPHRASINGS_DIR = Path("data/rephrasings")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")

    n = cfg.inoculation.n_rephrasings
    if n <= 1:
        log.info("n_rephrasings=%d — no rephrasings needed. Done.", n)
        return

    undesired = resolve_trait(cfg.trait_pair.undesired_trait)
    ip_prompt = build_ip_prompt(undesired.adjective, cfg.inoculation.template)
    style = cfg.inoculation.rephrasing_style
    model = args.rephrasing_model or cfg.inoculation.rephrasing_model
    backend = args.rephrasing_backend or cfg.inoculation.rephrasing_backend
    tag = undesired.adjective  # used in cache file names

    gpu_kwargs = dict(
        gpu_memory_utilization=args.gpu_memory_utilization,
        tensor_parallel_size=args.tensor_parallel_size,
    )

    log.info("Config: %s | trait: %s | n=%d | style=%s", cfg.condition_name, tag, n, style)
    log.info("IP prompt: %r", ip_prompt)

    bp = cfg.data_mix.benign_prefix

    # --- 1. IP rephrasings (always needed when harmful_prefix="rephrased") ---
    if cfg.data_mix.harmful_prefix == "rephrased":
        _run(
            "ip", ip_prompt, n, style, backend, model, api_key,
            REPHRASINGS_DIR / f"{tag}_ip_{style}_{n}.json",
            **gpu_kwargs,
        )

    # --- 2. Negated rephrasings (benign negated_rephrased fraction > 0) ---
    if bp.strategy == "split" and bp.negated_rephrased > 0:
        naive_neg = negate_naive(ip_prompt)
        log.info("Naive negation: %r", naive_neg)
        _run(
            "negated", naive_neg, n, style, backend, model, api_key,
            REPHRASINGS_DIR / f"{tag}_negated_{style}_{n}.json",
            **gpu_kwargs,
        )

    # --- 3. Neutral rephrasings (benign neutral_rephrased fraction > 0) ---
    if bp.strategy == "split" and bp.neutral_rephrased > 0:
        neutral = build_neutral_prompt()
        _run(
            "neutral", neutral, n, style, backend, model, api_key,
            REPHRASINGS_DIR / f"{tag}_neutral_{style}_{n}.json",
            **gpu_kwargs,
        )

    # --- 4. Semantic negations (benign negated_semantic fraction > 0) ---
    if bp.strategy == "split" and bp.negated_semantic > 0:
        cache = REPHRASINGS_DIR / f"{tag}_semantic_{n}.json"
        if cache.exists():
            log.info("[semantic_negated] Already cached at %s — skipping.", cache)
        else:
            log.info("[semantic_negated] Generating %d semantic negations of IP prompt...", n)
            negate_semantic(ip_prompt, n, model=model, api_key=api_key, cache_path=cache)
            log.info("[semantic_negated] Done → %s", cache)

    log.info("All rephrasings ready.")


def _run(
    label: str,
    prompt: str,
    n: int,
    style: str,
    backend: str,
    model: str,
    api_key: str | None,
    cache_path: Path,
    *,
    gpu_memory_utilization: float = 0.90,
    tensor_parallel_size: int = 1,
) -> None:
    if cache_path.exists():
        log.info("[%s] Already cached at %s — skipping.", label, cache_path)
        return
    log.info("[%s] Generating %d rephrasings (style=%s)...", label, n, style)
    generate_rephrasings(
        prompt, n,
        style=style,
        backend=backend,
        model=model,
        api_key=api_key,
        cache_path=cache_path,
        gpu_memory_utilization=gpu_memory_utilization,
        tensor_parallel_size=tensor_parallel_size,
    )
    log.info("[%s] Done → %s", label, cache_path)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate inoculation prompt rephrasings.")
    p.add_argument("--config", required=True, help="Path to experiment YAML config.")
    p.add_argument("--api-key", default=None, help="OpenAI API key (overrides env var).")
    # CLI overrides for backend (default: read from YAML)
    p.add_argument("--rephrasing-backend", default=None, choices=["api", "on_policy", "on_policy_hf"],
                   help="Override rephrasing_backend from config. "
                        "'on_policy'=vLLM, 'on_policy_hf'=HF Transformers.")
    p.add_argument("--rephrasing-model", default=None,
                   help="Override rephrasing_model from config.")
    # on_policy / vLLM options
    p.add_argument("--gpu-memory-utilization", type=float, default=0.90,
                   help="Fraction of GPU memory for vLLM (on_policy).")
    p.add_argument("--tensor-parallel-size", type=int, default=1,
                   help="Number of GPUs for tensor parallelism (on_policy).")
    return p.parse_args()


if __name__ == "__main__":
    main()
