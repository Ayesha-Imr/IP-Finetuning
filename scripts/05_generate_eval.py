"""
Script 05: Generate evaluation responses for all probes.

Reads:
  configs/examples/*.yaml     (experiment config with eval probes)

Produces:
  results/{experiment_id}/responses/   (one JSONL per model × probe × dataset)

Loads the base model once via vLLM with LoRA enabled, then generates responses
for the base model (no LoRA) and the fine-tuned model (LoRA adapter) across
all configured probes.

Resume-safe: skips model/probe/dataset combos whose output file already has
the expected number of records.

Requires a GPU with vLLM installed.

Usage
-----
    python scripts/05_generate_eval.py --config configs/examples/rrdn4_b50.yaml

    # Base model only (no LoRA):
    python scripts/05_generate_eval.py --config configs/examples/rrdn4_b50.yaml --base-only

    # Custom output + GPU settings:
    python scripts/05_generate_eval.py --config configs/examples/rrdn4_b50.yaml \\
        --output-dir /tmp/eval_responses --gpu-memory-utilization 0.85 --tensor-parallel-size 2
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ip_finetuning.config import ExperimentConfig
from ip_finetuning.evaluation.probes import resolve_probes

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path("results")


def main() -> None:
    args = _parse_args()
    cfg = ExperimentConfig.from_yaml(args.config)

    probes = resolve_probes(cfg.eval, cfg.trait_pair)
    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR / cfg.experiment_id / "responses"

    log.info("=" * 60)
    log.info("Phase 4a — Eval Response Generation")
    log.info("  Condition  : %s", cfg.condition_name)
    log.info("  Experiment : %s", cfg.experiment_id)
    log.info("  Backend    : %s", cfg.eval.inference_backend)
    log.info("  Probes     : %d", len(probes))
    log.info("  Prompts/probe: %d", cfg.eval.n_prompts)
    log.info("  Datasets   : %s", cfg.eval.datasets)
    log.info("  Base only  : %s", args.base_only)
    log.info("  Output     : %s", output_dir)
    log.info("=" * 60)

    if not probes:
        log.error("No probes configured in eval section. Nothing to do.")
        sys.exit(1)

    if cfg.eval.inference_backend == "vllm":
        from ip_finetuning.evaluation.inference import generate_eval_responses_vllm
        generate_eval_responses_vllm(
            cfg,
            probes,
            output_dir,
            hf_token=args.hf_token,
            gpu_memory_utilization=args.gpu_memory_utilization,
            tensor_parallel_size=args.tensor_parallel_size,
            base_only=args.base_only,
        )
    elif cfg.eval.inference_backend == "hf":
        from ip_finetuning.evaluation.inference import generate_eval_responses_hf
        generate_eval_responses_hf(
            cfg,
            probes,
            output_dir,
            hf_token=args.hf_token,
            base_only=args.base_only,
        )
    else:
        log.error("Unknown inference backend: %s", cfg.eval.inference_backend)
        sys.exit(1)

    log.info("Done. Responses written to %s", output_dir)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate eval responses for all probes.")
    p.add_argument("--config", required=True, help="Path to YAML experiment config.")
    p.add_argument("--base-only", action="store_true",
                   help="Only evaluate the base model (skip LoRA adapter).")
    p.add_argument("--hf-token", default=None,
                   help="HuggingFace token (default: HF_TOKEN env var).")
    p.add_argument("--output-dir", default=None,
                   help="Output directory for response JSONL files.")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.90,
                   help="vLLM GPU memory utilization (default: 0.90).")
    p.add_argument("--tensor-parallel-size", type=int, default=1,
                   help="Number of GPUs for tensor parallelism (default: 1).")
    return p.parse_args()


if __name__ == "__main__":
    main()
