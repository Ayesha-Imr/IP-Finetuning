"""
Model loading / unloading for mechanistic analysis.

Wraps HuggingFace + PEFT with automatic LoRA detection and merge.
Falls back to manual weight merging when PEFT doesn't support the
model's linear module type (e.g. Gemma4ClippableLinear).
"""

from __future__ import annotations

import gc
import json
import logging
import math
from typing import Optional

import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file as load_safetensors
from transformers import AutoModelForCausalLM, AutoTokenizer

log = logging.getLogger(__name__)


def _is_lora(model_id: str, hf_token: Optional[str]) -> bool:
    try:
        from huggingface_hub import file_exists
        return file_exists(model_id, "adapter_config.json", token=hf_token)
    except Exception:
        return False


def _manual_lora_merge(model, model_id: str, hf_token: Optional[str]) -> None:
    """Manually merge LoRA weights into base model when PEFT can't handle the architecture."""
    cfg_path = hf_hub_download(model_id, "adapter_config.json", token=hf_token)
    with open(cfg_path) as f:
        lora_cfg = json.load(f)

    r = lora_cfg["r"]
    alpha = lora_cfg["lora_alpha"]
    use_rslora = lora_cfg.get("use_rslora", False)
    scaling = alpha / math.sqrt(r) if use_rslora else alpha / r

    weights_path = hf_hub_download(model_id, "adapter_model.safetensors", token=hf_token)
    lora_weights = load_safetensors(weights_path)

    # Build a name→param dict once for O(1) lookup
    param_dict = {name: param for name, param in model.named_parameters()}

    merged_count = 0
    lora_a_keys = {k for k in lora_weights if "lora_A" in k}
    for a_key in sorted(lora_a_keys):
        b_key = a_key.replace("lora_A", "lora_B")
        if b_key not in lora_weights:
            continue

        # Derive module path from PEFT adapter key.
        module_path = a_key.replace(".lora_A.weight", "")
        for prefix in ("base_model.model.model.", "base_model.model."):
            if module_path.startswith(prefix):
                module_path = module_path[len(prefix):]
                break

        candidate = module_path + ".weight"

        # 1. Direct lookup
        target_param = param_dict.get(candidate)

        if target_param is None:
            # 2. Suffix match — handles cases where the model nests under an extra prefix
            suffix = "." + candidate
            for name, param in param_dict.items():
                if name.endswith(suffix) or name == candidate:
                    target_param = param
                    break

        if target_param is None:
            log.warning("  Could not find target param for %s — skipping", a_key)
            continue

        A = lora_weights[a_key].to(target_param.device, dtype=target_param.dtype)
        B = lora_weights[b_key].to(target_param.device, dtype=target_param.dtype)
        delta = (B @ A) * scaling
        target_param.data.add_(delta)
        merged_count += 1

    log.info("  Manual merge: applied %d LoRA weight pairs (r=%d, alpha=%d, scaling=%.4f)",
             merged_count, r, alpha, scaling)


def load_model(
    model_id: str,
    hf_token: Optional[str] = None,
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    log.info("Loading model: %s", model_id)
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)

    if _is_lora(model_id, hf_token):
        from peft import PeftConfig
        base_id = PeftConfig.from_pretrained(model_id, token=hf_token).base_model_name_or_path
        log.info("  LoRA adapter detected — base: %s", base_id)
        base = AutoModelForCausalLM.from_pretrained(
            base_id, torch_dtype=torch.float16, device_map="auto", token=hf_token,
        )

        try:
            from peft import PeftModel
            model = PeftModel.from_pretrained(base, model_id, token=hf_token)
            model = model.merge_and_unload()
        except (ValueError, TypeError) as e:
            log.warning("  PEFT merge failed (%s) — falling back to manual merge", e)
            _manual_lora_merge(base, model_id, hf_token)
            model = base
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float16, device_map="auto", token=hf_token,
        )

    model.eval()
    if torch.cuda.is_available():
        log.info("  VRAM: %.1f GB", torch.cuda.memory_allocated() / 1e9)
    return model, tokenizer


def unload_model(model, tokenizer) -> None:
    del model, tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    log.info("  Model unloaded, VRAM freed.")
