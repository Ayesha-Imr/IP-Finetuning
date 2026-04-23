"""
Script 04-KL: Fine-tune with Anchor-Neutral KL loss.

Same interface as 04_train.py but uses the KL trainer with three forward passes.

Usage
-----
    python scripts/04_train_kl.py \\
        --config configs/kl_experiments/french_playful_fixed_kl.yaml \\
        --kl-lambda 1.0 \\
        --keyword "French"

    # Lambda sweep:
    for lam in 0.1 0.5 1.0 5.0; do
        python scripts/04_train_kl.py \\
            --config configs/kl_experiments/french_playful_fixed_kl.yaml \\
            --kl-lambda $lam --keyword "French" --skip-upload
    done
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.training.upload import build_repo_id, upload_adapter
from ip_finetuning.utils.hf_sync import model_exists_on_hub

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

TRAINING_DIR = Path("data/training")
MODELS_DIR = Path("models")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)

    kl_lambda = args.kl_lambda
    keyword = args.keyword
    neutral_prompt = args.neutral_prompt

    # Load the base config separately to find the training data
    base_cfg = ExperimentConfig.from_yaml(args.config)
    data_path = TRAINING_DIR / f"{base_cfg.experiment_id}.jsonl"

    # Override condition name with lambda suffix for unique experiment IDs
    suffix = f"_lam{kl_lambda}".replace(".", "p")
    cfg.condition_name = f"{cfg.condition_name}{suffix}"

    output_dir = Path(args.output_dir) if args.output_dir else MODELS_DIR / cfg.experiment_id

    # Write the resolved config so eval scripts can reference it
    resolved_config_dir = Path("configs/kl_experiments/resolved")
    resolved_config_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path = resolved_config_dir / f"{cfg.condition_name}.yaml"
    _write_resolved_config(cfg, resolved_config_path)

    if not data_path.exists():
        log.error("Training data not found: %s\nRun scripts 01-03 first.", data_path)
        sys.exit(1)

    # Resume check
    adapter_dir = output_dir / "adapter"
    if adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists():
        log.info("Adapter already trained at %s — skipping.", adapter_dir)
        _maybe_upload(args, cfg, adapter_dir)
        return

    hf_token = args.hf_token or os.environ.get("HF_TOKEN")
    if not args.skip_upload and hf_token:
        repo_id = build_repo_id(cfg)
        if model_exists_on_hub(repo_id, hf_token):
            log.info("Model already on Hub: %s — nothing to do.", repo_id)
            return

    # Train
    log.info("=" * 60)
    log.info("Experiment:  %s", cfg.experiment_id)
    log.info("Condition:   %s", cfg.condition_name)
    log.info("Training:    Anchor-Neutral KL")
    log.info("λ (KL):      %.2f", kl_lambda)
    log.info("Keyword:     %r", keyword)
    log.info("Neutral:     %r", neutral_prompt)
    log.info("Data:        %s (%d lines)", data_path, _count_lines(data_path))
    log.info("Model:       %s", cfg.training.base_model_id)
    log.info("Output:      %s", output_dir)
    log.info("=" * 60)

    from ip_finetuning.training.kl_train import train_kl

    t0 = time.time()
    adapter_dir = train_kl(
        cfg, data_path, output_dir,
        kl_lambda=kl_lambda,
        keyword=keyword,
        neutral_prompt=neutral_prompt,
    )
    elapsed = time.time() - t0
    log.info("Training finished in %.0fs. Adapter at: %s", elapsed, adapter_dir)

    _maybe_upload(args, cfg, adapter_dir)


def _maybe_upload(args, cfg, adapter_dir):
    if args.skip_upload:
        log.info("--skip-upload set; not pushing to Hub.")
        return
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")
    if not hf_token:
        log.warning("No HF_TOKEN found; skipping upload.")
        return
    merge = args.merge or cfg.training.merge_before_upload
    final_repo = upload_adapter(adapter_dir, cfg, hf_token, merge=merge)
    log.info("Uploaded to: %s", final_repo)


def _write_resolved_config(cfg, path: Path) -> None:
    """Write the resolved config (with lambda-suffixed condition name) as YAML."""
    from dataclasses import asdict
    import yaml
    with open(path, "w") as f:
        yaml.dump(asdict(cfg), f, default_flow_style=False, sort_keys=False)
    log.info("Resolved config written → %s", path)


def _count_lines(path: Path) -> int:
    with open(path) as f:
        return sum(1 for _ in f)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fine-tune with Anchor-Neutral KL loss.")
    p.add_argument("--config", required=True, help="Path to YAML experiment config.")
    p.add_argument("--kl-lambda", type=float, required=True, help="KL loss weight (λ).")
    p.add_argument("--keyword", required=True, help="Bare trait keyword for KL target.")
    p.add_argument("--neutral-prompt", default="You are a helpful assistant.",
                   help="Neutral anchor prompt.")
    p.add_argument("--hf-token", default=None, help="HuggingFace write token.")
    p.add_argument("--merge", action="store_true", help="Merge LoRA before uploading.")
    p.add_argument("--skip-upload", action="store_true", help="Don't push to Hub.")
    p.add_argument("--output-dir", default=None, help="Override output directory.")
    return p.parse_args()


if __name__ == "__main__":
    main()
