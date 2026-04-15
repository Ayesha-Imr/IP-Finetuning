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
    """Generate eval responses for all probes using vLLM.

    Attempts LoRA hot-swap (single engine load) first. If the model architecture
    does not support vLLM LoRA serving (e.g. Gemma 4), falls back to merging the
    adapter to disk and loading the merged model without LoRA — two separate
    engine loads (base, then merged FT model).

    Resume-safe: skips model/probe/dataset combos that already have the expected
    number of records.

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
    from transformers import AutoTokenizer
    import gc
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

    sampling_params = SamplingParams(
        temperature=eval_cfg.temperature,
        max_tokens=eval_cfg.max_new_tokens,
        seed=eval_cfg.seed,
    )

    def _make_llm(model_path: str, enable_lora: bool, lora_rank: int = 64) -> LLM:
        kwargs = dict(
            model=model_path,
            dtype="float16",
            gpu_memory_utilization=gpu_memory_utilization,
            trust_remote_code=True,
            tensor_parallel_size=tensor_parallel_size,
            enable_lora=enable_lora,
        )
        if enable_lora:
            kwargs["max_lora_rank"] = lora_rank
        return LLM(**kwargs)

    # --- Attempt LoRA hot-swap (single LLM) ---
    lora_supported = False
    llm = None
    if not base_only and adapter_path is not None:
        try:
            llm = _make_llm(base_model, enable_lora=True, lora_rank=max_lora_rank)
            lora_supported = True
        except (ValueError, RuntimeError) as e:
            err_msg = str(e).lower()
            if "does not support lora" not in err_msg and "engine core initialization failed" not in err_msg:
                raise
            log.warning(
                "vLLM LoRA hot-swap not supported for this architecture (%s). "
                "Falling back to merge-adapter-then-serve.",
                base_model,
            )

    if llm is None:
        llm = _make_llm(base_model, enable_lora=False)

    if lora_supported:
        # Single LLM, hot-swap between base and FT adapter
        from vllm.lora.request import LoRARequest
        from ip_finetuning.training.upload import build_repo_id
        ft_model_id = build_repo_id(config)
        lora_req = LoRARequest("ft", 1, str(adapter_path))
        models = [("base", None), (ft_model_id, lora_req)]
        _run_vllm_eval_loop(llm, tokenizer, sampling_params, models, probes, eval_cfg, config, output_dir)
        del llm
        gc.collect()
        torch.cuda.empty_cache()
    else:
        # Two-LLM approach: base model first, then merged FT model
        # 1. Base model
        if not base_only:
            models_base = [("base", None)]
            _run_vllm_eval_loop(llm, tokenizer, sampling_params, models_base, probes, eval_cfg, config, output_dir)
            del llm
            gc.collect()
            torch.cuda.empty_cache()

        if not base_only and adapter_path is not None:
            # 2. Merged FT model
            merged_path = _merge_adapter_to_disk(base_model, adapter_path, config, hf_token)
            ft_llm = _make_llm(str(merged_path), enable_lora=False)
            from ip_finetuning.training.upload import build_repo_id
            ft_model_id = build_repo_id(config)
            models_ft = [(ft_model_id, None)]
            _run_vllm_eval_loop(ft_llm, tokenizer, sampling_params, models_ft, probes, eval_cfg, config, output_dir)
            del ft_llm
            gc.collect()
            torch.cuda.empty_cache()
        elif base_only:
            models_base = [("base", None)]
            _run_vllm_eval_loop(llm, tokenizer, sampling_params, models_base, probes, eval_cfg, config, output_dir)
            del llm
            gc.collect()
            torch.cuda.empty_cache()

    log.info("All eval generation complete. VRAM released.")
    return output_dir


def _run_vllm_eval_loop(llm, tokenizer, sampling_params, models, probes, eval_cfg, config, output_dir: Path) -> None:
    """Inner loop: iterate datasets × models × probes and write JSONL outputs."""
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


def _merge_adapter_to_disk(base_model: str, adapter_path: Path, config, hf_token: str | None) -> Path:
    """Merge LoRA adapter into base model and save to local directory.

    Must use unsloth for Gemma 4 because:
    - The adapter targets Gemma4ClippableLinear modules (custom to unsloth)
    - Vanilla PEFT can't load adapters onto these module types
    - unsloth's save_pretrained_merged correctly saves ALL weights (including
      k_norm) in standard HF format that vLLM can load

    Pass the adapter_path directly to FastModel.from_pretrained — unsloth
    auto-detects the adapter, reads adapter_config.json for the base model,
    and loads both. Then save_pretrained_merged writes a clean full-precision
    checkpoint.
    """
    import gc
    import torch

    merged_dir = Path("models") / f"{config.experiment_id}_merged"
    if merged_dir.exists() and any(merged_dir.iterdir()):
        log.info("Merged model already on disk at %s — reusing.", merged_dir)
        return merged_dir

    merged_dir.mkdir(parents=True, exist_ok=True)
    log.info("Merging LoRA adapter into base model → %s ...", merged_dir)
    hf_kwargs = {"token": hf_token} if hf_token else {}

    from unsloth import FastModel

    _model = _tokenizer = None
    try:
        log.info("Loading adapter via unsloth (auto-detects base model from adapter_config.json)...")
        _model, _tokenizer = FastModel.from_pretrained(
            model_name=str(adapter_path),  # unsloth detects adapter + loads base automatically
            dtype=torch.float16,
            max_seq_length=2048,
            load_in_4bit=False,
            **hf_kwargs,
        )
        log.info("Saving merged 16-bit model (save_pretrained_merged)...")
        # save_pretrained_merged writes all weights including k_norm in standard HF format
        _model.save_pretrained_merged(str(merged_dir), _tokenizer, save_method="merged_16bit")
        log.info("Merged model saved → %s", merged_dir)
    finally:
        del _model, _tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()

    return merged_dir


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
