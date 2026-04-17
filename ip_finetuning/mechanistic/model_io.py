"""
Model loading / unloading for mechanistic analysis.

Wraps HuggingFace + PEFT with automatic LoRA detection and merge.
"""

from __future__ import annotations

import gc
import logging
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

log = logging.getLogger(__name__)


def _is_lora(model_id: str, hf_token: Optional[str]) -> bool:
    try:
        from huggingface_hub import file_exists
        return file_exists(model_id, "adapter_config.json", token=hf_token)
    except Exception:
        return False


def load_model(
    model_id: str,
    hf_token: Optional[str] = None,
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    log.info("Loading model: %s", model_id)
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)

    if _is_lora(model_id, hf_token):
        from peft import PeftConfig, PeftModel
        base_id = PeftConfig.from_pretrained(model_id, token=hf_token).base_model_name_or_path
        log.info("  LoRA adapter detected — base: %s", base_id)
        base = AutoModelForCausalLM.from_pretrained(
            base_id, torch_dtype=torch.float16, device_map="auto", token=hf_token,
        )
        model = PeftModel.from_pretrained(base, model_id, token=hf_token)
        model = model.merge_and_unload()
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
