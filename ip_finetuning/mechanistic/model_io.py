"""
Model loading / unloading for mechanistic analysis.

Wraps HuggingFace + PEFT with automatic LoRA detection and merge.
For architectures where vanilla PEFT fails (e.g. Gemma 4 with
Gemma4ClippableLinear), falls back to unsloth's merge — the same
approach used by the eval pipeline in evaluation/inference.py.
"""

from __future__ import annotations

import gc
import logging
import shutil
from pathlib import Path
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

log = logging.getLogger(__name__)

_MERGED_CACHE = Path("models") / "mechanistic_merged"


def _is_lora(model_id: str, hf_token: Optional[str]) -> bool:
    try:
        from huggingface_hub import file_exists
        return file_exists(model_id, "adapter_config.json", token=hf_token)
    except Exception:
        return False


def _merge_via_unsloth(model_id: str, hf_token: Optional[str]) -> Path:
    """Use unsloth to merge LoRA adapter into base model on disk."""
    slug = model_id.replace("/", "__")
    merged_dir = _MERGED_CACHE / slug

    if merged_dir.exists() and any(merged_dir.iterdir()):
        log.info("  Reusing cached merged model at %s", merged_dir)
        return merged_dir

    merged_dir.mkdir(parents=True, exist_ok=True)
    log.info("  Merging via unsloth → %s ...", merged_dir)

    from huggingface_hub import snapshot_download
    adapter_path = snapshot_download(model_id, token=hf_token)

    from unsloth import FastModel
    hf_kwargs = {"token": hf_token} if hf_token else {}
    _model, _tokenizer = FastModel.from_pretrained(
        model_name=str(adapter_path),
        dtype=torch.float16,
        max_seq_length=2048,
        load_in_4bit=False,
        **hf_kwargs,
    )
    _model.save_pretrained_merged(str(merged_dir), _tokenizer, save_method="merged_16bit")

    del _model, _tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    log.info("  Merged model saved → %s", merged_dir)
    return merged_dir


def load_model(
    model_id: str,
    hf_token: Optional[str] = None,
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    log.info("Loading model: %s", model_id)

    if _is_lora(model_id, hf_token):
        from peft import PeftConfig
        base_id = PeftConfig.from_pretrained(model_id, token=hf_token).base_model_name_or_path
        log.info("  LoRA adapter detected — base: %s", base_id)

        # Try PEFT merge first (works for most architectures)
        try:
            from peft import PeftModel
            base = AutoModelForCausalLM.from_pretrained(
                base_id, torch_dtype=torch.float16, device_map="auto", token=hf_token,
            )
            model = PeftModel.from_pretrained(base, model_id, token=hf_token)
            model = model.merge_and_unload()
            tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)
        except (ValueError, TypeError, RuntimeError) as e:
            log.warning("  PEFT merge failed (%s) — falling back to unsloth merge", e)
            # Free any partially loaded model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            merged_dir = _merge_via_unsloth(model_id, hf_token)
            model = AutoModelForCausalLM.from_pretrained(
                str(merged_dir), torch_dtype=torch.float16, device_map="auto",
            )
            tokenizer = AutoTokenizer.from_pretrained(str(merged_dir))
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float16, device_map="auto", token=hf_token,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)

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
