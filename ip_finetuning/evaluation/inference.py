"""
vLLM-based eval inference with LoRA hot-swap.

Generates model responses for eval probes, evaluating both the base model
(no LoRA) and the fine-tuned model (with LoRA adapter) in a single engine load.

Public API:
    generate_eval_responses_vllm(config, probes, output_dir, ...)
    generate_eval_responses_hf(config, probes, output_dir, ...)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ip_finetuning.datasets import load_prompts
from ip_finetuning.evaluation.probes import ResolvedProbe
from ip_finetuning.utils.io import read_jsonl, write_jsonl

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# vLLM backend (batched, LoRA hot-swap)
# ---------------------------------------------------------------------------

def generate_eval_responses_vllm(
    config,
    probes: list[ResolvedProbe],
    output_dir: Path,
    *,
    hf_token: str | None = None,
    gpu_memory_utilization: float = 0.90,
    tensor_parallel_size: int = 1,
    base_only: bool = False,
) -> Path:
    """Generate eval responses for all probes using vLLM + LoRA hot-swap.

    Evaluates both the base model (no LoRA) and the FT model (LoRA adapter)
    in a single engine load. Resume-safe: skips model/probe combos that
    already have the expected number of records.

    Args:
        config:  ExperimentConfig.
        probes:  Resolved probe list.
        output_dir: Directory for output JSONL files.
        hf_token: Optional HuggingFace token for gated models.
        gpu_memory_utilization: vLLM GPU memory fraction.
        tensor_parallel_size: Number of GPUs.
        base_only: If True, only evaluate the base model (skip LoRA).

    Returns:
        Path to output directory containing JSONL files.
    """
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest
    from transformers import AutoTokenizer
    import torch

    base_model = config.training.base_model_id
    eval_cfg = config.eval
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download adapter and read rank
    adapter_path = None
    max_lora_rank = 64  # fallback
    if not base_only:
        adapter_path = _download_adapter(config, hf_token)
        adapter_cfg = json.loads((adapter_path / "adapter_config.json").read_text())
        max_lora_rank = adapter_cfg.get("r", max_lora_rank)

    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        **({"token": hf_token} if hf_token else {}),
    )

    llm = LLM(
        model=base_model,
        dtype="float16",
        gpu_memory_utilization=gpu_memory_utilization,
        trust_remote_code=True,
        enable_lora=not base_only,
        **({"max_lora_rank": max_lora_rank} if not base_only else {}),
        tensor_parallel_size=tensor_parallel_size,
    )

    sampling_params = SamplingParams(
        temperature=eval_cfg.temperature,
        max_tokens=eval_cfg.max_new_tokens,
        seed=eval_cfg.seed,
    )

    # Model IDs to evaluate
    models = [("base", None)]
    if not base_only and adapter_path is not None:
        lora_req = LoRARequest("ft", 1, str(adapter_path))
        from ip_finetuning.training.upload import build_repo_id
        ft_model_id = build_repo_id(config)
        models.append((ft_model_id, lora_req))

    for dataset_name in eval_cfg.datasets:
        prompts = load_prompts(
            dataset_name,
            n=eval_cfg.n_prompts,
            offset=eval_cfg.eval_offset,
            seed=eval_cfg.seed,
        )
        for model_id, lora_request in models:
            for probe in probes:
                out_path = output_dir / f"{_safe_filename(model_id)}_{probe.name}_{dataset_name}.jsonl"
                expected = len(prompts)

                if out_path.exists():
                    existing = sum(1 for _ in open(out_path))
                    if existing >= expected:
                        log.info("[%s/%s/%s] already complete (%d lines) — skipping.",
                                 model_id, probe.name, dataset_name, existing)
                        continue
                    log.warning("[%s/%s/%s] partial (%d/%d) — regenerating.",
                                model_id, probe.name, dataset_name, existing, expected)

                prompt_strings = [
                    _build_eval_prompt(tokenizer, probe.system_prompt, q)
                    for q in prompts
                ]

                log.info("[%s/%s/%s] Generating %d responses...",
                         model_id, probe.name, dataset_name, len(prompt_strings))

                outputs = llm.generate(
                    prompt_strings,
                    sampling_params,
                    **({"lora_request": lora_request} if lora_request else {}),
                )

                records = []
                for qi, (query, output) in enumerate(zip(prompts, outputs)):
                    records.append({
                        "model_id": model_id,
                        "condition_name": config.condition_name,
                        "desired_trait": config.trait_pair.desired_trait,
                        "undesired_trait": config.trait_pair.undesired_trait,
                        "probe_name": probe.name,
                        "probe_category": probe.category,
                        "dataset": dataset_name,
                        "query_idx": qi,
                        "system_prompt": probe.system_prompt,
                        "user_query": query,
                        "response": output.outputs[0].text,
                    })

                write_jsonl(records, out_path)
                log.info("[%s/%s/%s] Wrote %d records → %s",
                         model_id, probe.name, dataset_name, len(records), out_path)

    del llm
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    log.info("All eval generation complete. VRAM released.")

    return output_dir


# ---------------------------------------------------------------------------
# HuggingFace Transformers backend (PEFT, mech-interp seam)
# ---------------------------------------------------------------------------

def generate_eval_responses_hf(
    config,
    probes: list[ResolvedProbe],
    output_dir: Path,
    *,
    hf_token: str | None = None,
    base_only: bool = False,
) -> Path:
    """Generate eval responses using HF Transformers + PEFT (slower, mech-interp seam).

    Same interface as vLLM backend but uses standard HF generate().
    Useful for hook access for mechanistic interpretability.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_model = config.training.base_model_id
    eval_cfg = config.eval
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        trust_remote_code=True,
        **({"token": hf_token} if hf_token else {}),
    )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        **({"token": hf_token} if hf_token else {}),
    )

    models_to_eval = [("base", model)]

    if not base_only:
        from peft import PeftModel
        adapter_path = _download_adapter(config, hf_token)
        ft_model = PeftModel.from_pretrained(model, str(adapter_path))
        from ip_finetuning.training.upload import build_repo_id
        ft_model_id = build_repo_id(config)
        models_to_eval.append((ft_model_id, ft_model))

    for dataset_name in eval_cfg.datasets:
        prompts = load_prompts(
            dataset_name,
            n=eval_cfg.n_prompts,
            offset=eval_cfg.eval_offset,
            seed=eval_cfg.seed,
        )
        for model_id, cur_model in models_to_eval:
            for probe in probes:
                out_path = output_dir / f"{_safe_filename(model_id)}_{probe.name}_{dataset_name}.jsonl"
                expected = len(prompts)

                if out_path.exists():
                    existing = sum(1 for _ in open(out_path))
                    if existing >= expected:
                        log.info("[%s/%s/%s] already complete — skipping.", model_id, probe.name, dataset_name)
                        continue

                log.info("[%s/%s/%s] Generating %d responses (HF backend)...",
                         model_id, probe.name, dataset_name, len(prompts))

                records = []
                for qi, query in enumerate(prompts):
                    prompt_text = _build_eval_prompt(tokenizer, probe.system_prompt, query)
                    inputs = tokenizer(prompt_text, return_tensors="pt").to(cur_model.device)
                    with torch.no_grad():
                        out_ids = cur_model.generate(
                            **inputs,
                            max_new_tokens=eval_cfg.max_new_tokens,
                            temperature=eval_cfg.temperature,
                            do_sample=True,
                        )
                    response = tokenizer.decode(
                        out_ids[0][inputs["input_ids"].shape[1]:],
                        skip_special_tokens=True,
                    )
                    records.append({
                        "model_id": model_id,
                        "condition_name": config.condition_name,
                        "desired_trait": config.trait_pair.desired_trait,
                        "undesired_trait": config.trait_pair.undesired_trait,
                        "probe_name": probe.name,
                        "probe_category": probe.category,
                        "dataset": dataset_name,
                        "query_idx": qi,
                        "system_prompt": probe.system_prompt,
                        "user_query": query,
                        "response": response,
                    })

                write_jsonl(records, out_path)
                log.info("[%s/%s/%s] Wrote %d records → %s",
                         model_id, probe.name, dataset_name, len(records), out_path)

    del model
    if not base_only:
        del ft_model
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    log.info("All eval generation complete (HF). VRAM released.")

    return output_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_eval_prompt(tokenizer, system_prompt: str, user_query: str) -> str:
    """Build a chat-formatted prompt string for eval."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_query})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def _download_adapter(config, hf_token: str | None = None) -> Path:
    """Download fine-tuned adapter from HuggingFace Hub.

    Returns path to local adapter directory.
    """
    from huggingface_hub import snapshot_download
    from ip_finetuning.training.upload import build_repo_id

    repo_id = build_repo_id(config)
    log.info("Downloading adapter: %s", repo_id)
    local_dir = snapshot_download(
        repo_id,
        **({"token": hf_token} if hf_token else {}),
    )
    return Path(local_dir)


def _safe_filename(s: str) -> str:
    """Convert a string to a safe filename component."""
    return s.replace("/", "_").replace("\\", "_").replace(" ", "_")
