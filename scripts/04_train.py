"""
Script 04: Fine-tune a LoRA adapter and upload to HuggingFace Hub.

Reads:
  data/training/{experiment_id}.jsonl   (output of script 03)

Produces:
  models/{experiment_id}/adapter/       (local LoRA adapter + tokenizer)
  models/{experiment_id}/training_meta.json
  HuggingFace Hub: {hf_upload_org}/{base_model_short}-{condition}-{hash}

Requires a GPU (A100 80GB recommended) with Unsloth + TRL installed.

Resume-safe: if the model already exists on HuggingFace Hub, training is skipped.

Usage
-----
    python scripts/04_train.py --config configs/examples/rrdn4_b50.yaml

    # Skip upload (local training only):
    python scripts/04_train.py --config configs/examples/rrdn4_b50.yaml --skip-upload

    # Merge LoRA into base before uploading:
    python scripts/04_train.py --config configs/examples/rrdn4_b50.yaml --merge

    # Custom HF token and output directory:
    python scripts/04_train.py --config configs/examples/rrdn4_b50.yaml \\
        --hf-token hf_xxx --output-dir /tmp/my_model
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

    # --- Resolve paths ---
    data_path = TRAINING_DIR / f"{cfg.experiment_id}.jsonl"
    output_dir = Path(args.output_dir) if args.output_dir else MODELS_DIR / cfg.experiment_id

    if not data_path.exists():
        log.error("Training data not found: %s\nRun script 03 first.", data_path)
        sys.exit(1)

    # --- Resume check: skip if model already exists (locally or on Hub) ---
    hf_token = args.hf_token or os.environ.get("HF_TOKEN")
    repo_id = build_repo_id(cfg)
    adapter_dir = output_dir / "adapter"

    # Local check: if adapter already trained, skip training
    if adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists():
        log.info("Adapter already trained locally at %s — skipping training.", adapter_dir)
        # Still try upload if not --skip-upload
        if not args.skip_upload and hf_token:
            if not model_exists_on_hub(repo_id, hf_token):
                log.info("But not yet on Hub — will upload now.")
                merge = args.merge or cfg.training.merge_before_upload
                final_repo = upload_adapter(adapter_dir, cfg, hf_token, merge=merge)
                log.info("Uploaded to: %s", final_repo)
            else:
                log.info("Already on Hub too: %s", repo_id)
        return

    # Hub check: if already on Hub and we're not merging/retraining, skip
    if not args.skip_upload and hf_token:
        if model_exists_on_hub(repo_id, hf_token):
            log.info("Model already on Hub: %s — nothing to do.", repo_id)
            return

    # --- Train ---
    log.info("=" * 60)
    log.info("Experiment: %s", cfg.experiment_id)
    log.info("Condition:  %s", cfg.condition_name)
    log.info("Data:       %s (%d lines)", data_path, _count_lines(data_path))
    log.info("Model:      %s", cfg.training.base_model_id)
    log.info("Output:     %s", output_dir)
    log.info("Hub repo:   %s", repo_id)
    log.info("=" * 60)

    from ip_finetuning.training.train import train

    t0 = time.time()
    adapter_dir = train(cfg, data_path, output_dir)  # overwrites the pre-check assignment
    elapsed = time.time() - t0

    log.info("Training finished in %.0fs. Adapter at: %s", elapsed, adapter_dir)

    # --- Upload ---
    if args.skip_upload:
        log.info("--skip-upload set; not pushing to Hub.")
        return

    if not hf_token:
        log.warning("No HF_TOKEN found; skipping upload. Set HF_TOKEN or use --hf-token.")
        return

    merge = args.merge or cfg.training.merge_before_upload
    final_repo = upload_adapter(adapter_dir, cfg, hf_token, merge=merge)
    log.info("Uploaded to: %s", final_repo)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_lines(path: Path) -> int:
    with open(path) as f:
        return sum(1 for _ in f)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fine-tune a LoRA adapter with Unsloth + TRL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--config", required=True, help="Path to YAML experiment config.")
    p.add_argument("--hf-token", default=None, help="HuggingFace write token (default: $HF_TOKEN).")
    p.add_argument("--merge", action="store_true", help="Merge LoRA into base model before uploading.")
    p.add_argument("--skip-upload", action="store_true", help="Train locally only; don't push to Hub.")
    p.add_argument("--output-dir", default=None, help="Override local output directory.")
    return p.parse_args()


if __name__ == "__main__":
    main()
