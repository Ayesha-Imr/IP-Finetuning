"""
Upload trained adapters (or merged models) to HuggingFace Hub.

Model naming convention:
    {hf_upload_org}/{base_model_short}-{condition_name}-{short_hash}
    e.g. ayesha1505/Qwen2.5-7B-RRDN4-b50-a1b2c3d4

Resume-safe: skips upload if the repo already exists on the Hub.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from pathlib import Path

import yaml

from ip_finetuning.utils.hashing import short_hash
from ip_finetuning.utils.hf_sync import model_exists_on_hub, push_model

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_repo_id(config) -> str:
    """Compute the HuggingFace repo id for a given experiment config.

    Args:
        config: ExperimentConfig dataclass.

    Returns:
        Repo id string, e.g. "ayesha1505/Qwen2.5-7B-RRDN4-b50-a1b2c3d4".
    """
    tc = config.training
    base_short = _model_short_name(tc.base_model_id)
    h = short_hash(config)
    return f"{tc.hf_upload_org}/{base_short}-{config.condition_name}-{h}"


def upload_adapter(local_dir, config, hf_token, merge=False):
    """Upload a trained adapter (or merged model) to HuggingFace Hub.

    Args:
        local_dir: Path to the local adapter directory (output of train()).
        config:    ExperimentConfig dataclass.
        hf_token:  HuggingFace write token.
        merge:     If True, merge LoRA into base model and push full weights.

    Returns:
        The repo id on HuggingFace Hub.
    """
    local_dir = Path(local_dir)
    repo_id = build_repo_id(config)

    # Resume-safe: skip if already uploaded
    if model_exists_on_hub(repo_id, hf_token):
        log.info("Model already on Hub: %s — skipping upload.", repo_id)
        return repo_id

    if merge:
        _upload_merged(local_dir, config, repo_id, hf_token)
    else:
        push_model(local_dir, repo_id, hf_token, private=True)

    # Upload model card alongside the adapter
    _upload_model_card(repo_id, config, hf_token)
    log.info("Upload complete: %s", repo_id)
    return repo_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _model_short_name(model_id: str) -> str:
    """Extract a concise model name from a HuggingFace model id.

    Examples:
        "Qwen/Qwen2.5-7B-Instruct"       → "Qwen2.5-7B"
        "meta-llama/Llama-3.1-8B-Instruct" → "Llama-3.1-8B"
        "google/gemma-2-12b-it"            → "gemma-2-12b"
        "unsloth/Qwen2.5-7B-Instruct"     → "Qwen2.5-7B"
    """
    # Take the part after the org slash
    name = model_id.split("/")[-1] if "/" in model_id else model_id
    # Remove common suffixes
    for suffix in ("-Instruct", "-instruct", "-it", "-chat", "-Chat"):
        name = name.removesuffix(suffix)
    return name


def _upload_merged(local_dir, config, repo_id, hf_token):
    """Merge LoRA into base model and push the merged 16-bit model."""
    from unsloth import FastLanguageModel

    log.info("Merging LoRA adapter into base model for upload...")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.training.base_model_id,
        max_seq_length=config.training.max_seq_length,
        dtype=None,
        load_in_4bit=config.training.load_in_4bit,
    )

    # Load the adapter weights on top of the base model
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, str(local_dir))

    model.push_to_hub_merged(
        repo_id,
        tokenizer,
        save_method="merged_16bit",
        token=hf_token,
        private=True,
    )


def _upload_model_card(repo_id, config, hf_token):
    """Generate and upload a model card (README.md) with the training config."""
    from huggingface_hub import HfApi

    tc = config.training
    config_yaml = yaml.dump(asdict(config), default_flow_style=False, sort_keys=False)

    card = f"""---
tags:
  - ip-finetuning
  - inoculation-prompting
  - lora
base_model: {tc.base_model_id}
---

# {repo_id.split("/")[-1]}

LoRA adapter fine-tuned with [IP-Finetuning](https://github.com/ayesha1505/IP-Finetuning) pipeline.

| Field | Value |
|---|---|
| **Base model** | `{tc.base_model_id}` |
| **Condition** | `{config.condition_name}` |
| **Experiment ID** | `{config.experiment_id}` |
| **LoRA rank** | {tc.lora_r} |
| **Epochs** | {tc.epochs} |
| **Learning rate** | {tc.learning_rate} |
| **Desired trait** | {config.trait_pair.desired_trait} |
| **Undesired trait** | {config.trait_pair.undesired_trait} |

<details>
<summary>Full config (YAML)</summary>

```yaml
{config_yaml}```
</details>
"""

    api = HfApi(token=hf_token)
    api.upload_file(
        path_or_fileobj=card.encode(),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
    )
