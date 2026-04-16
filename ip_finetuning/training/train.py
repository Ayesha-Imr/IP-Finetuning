"""
Fine-tuning with Unsloth + TRL SFTTrainer.

Three public entry points, deliberately separated for mech-interp extensibility:

    model, tokenizer = load_model(config.training)
    # ← attach forward hooks here for activation extraction
    model = create_lora_adapter(model, config.training)
    output_dir = train(config, data_path, output_dir)

All GPU-only imports (torch, unsloth, trl, transformers, peft) are lazy —
the module is importable on CPU without those libraries installed.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_model(config):
    """Load a base model via Unsloth.

    Args:
        config: TrainingConfig dataclass.

    Returns:
        (model, tokenizer) tuple. The model is on GPU in the appropriate dtype.
    """
    from unsloth import FastLanguageModel

    log.info("Loading base model: %s (4bit=%s, max_seq=%d)",
             config.base_model_id, config.load_in_4bit, config.max_seq_length)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.base_model_id,
        max_seq_length=config.max_seq_length,
        dtype=None,                     # auto-detect (bf16 on A100)
        load_in_4bit=config.load_in_4bit,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


def create_lora_adapter(model, config):
    """Attach a LoRA adapter to a base model.

    Args:
        model:  Model returned by load_model().
        config: TrainingConfig dataclass.

    Returns:
        The same model, now with trainable LoRA parameters.
    """
    from unsloth import FastLanguageModel

    log.info("Creating LoRA adapter: r=%d, alpha=%d, rslora=%s",
             config.lora_r, config.lora_alpha, config.use_rslora)

    model = FastLanguageModel.get_peft_model(
        model,
        r=config.lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=config.seed,
        use_rslora=config.use_rslora,
    )
    return model


def train(config, data_path, output_dir, stage_paths=None):
    """Full training orchestrator.

    Args:
        config:      ExperimentConfig dataclass.
        data_path:   Path to the training JSONL (output of 03_mix_data.py).
                     For curriculum mode, this is the stage-0 JSONL.
        output_dir:  Local directory to save the adapter + metadata.
        stage_paths: Optional list of Paths to per-stage training JSONLs.
                     When provided, curriculum training is activated.

    Returns:
        Path to the saved adapter directory.
    """
    import torch
    from unsloth import is_bfloat16_supported  # must be first unsloth import
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    tc = config.training
    data_path = Path(data_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # ---- 1. Load model + LoRA ----
    model, tokenizer = load_model(tc)
    model = create_lora_adapter(model, tc)

    # ---- 2. Load & prepare dataset ----
    dataset = _load_dataset(data_path, tokenizer)
    log.info("Training dataset: %d examples.", len(dataset))

    # ---- 3. Training arguments (SFTConfig = TrainingArguments + SFT-specific fields) ----
    use_bf16 = is_bfloat16_supported()
    save_steps = tc.save_steps if tc.save_steps is not None else 999_999

    training_args = SFTConfig(
        output_dir=str(output_dir),
        per_device_train_batch_size=tc.per_device_batch_size,
        gradient_accumulation_steps=tc.gradient_accumulation_steps,
        warmup_steps=tc.warmup_steps,
        num_train_epochs=tc.epochs,
        learning_rate=tc.learning_rate,
        fp16=not use_bf16,
        bf16=use_bf16,
        logging_steps=tc.logging_steps,
        optim=tc.optim,
        weight_decay=tc.weight_decay,
        lr_scheduler_type=tc.lr_scheduler_type,
        max_grad_norm=tc.max_grad_norm,
        seed=tc.seed,
        save_steps=save_steps,
        report_to=[],
        # SFT-specific
        dataset_text_field="text",
        max_seq_length=tc.max_seq_length,
        dataset_num_proc=4,
        packing=tc.packing,
    )

    # ---- 4. SFTTrainer ----
    import inspect as _inspect
    _sft_kwarg = "processing_class" if "processing_class" in _inspect.signature(SFTTrainer.__init__).parameters else "tokenizer"

    curriculum_cb = None
    if stage_paths and config.curriculum:
        from ip_finetuning.training.curriculum_callback import create_curriculum_callback
        stage_datasets = [_load_dataset(p, tokenizer) for p in stage_paths]
        stage_fractions = [s.until_fraction for s in config.curriculum.stages]
        curriculum_cb = create_curriculum_callback(stage_datasets, stage_fractions)
        log.info("Curriculum: %d stages pre-loaded.", len(stage_datasets))
        # Use stage 0 as the initial dataset
        dataset = stage_datasets[0]

    callbacks = [curriculum_cb] if curriculum_cb else []
    trainer = SFTTrainer(
        model=model,
        **{_sft_kwarg: tokenizer},
        train_dataset=dataset,
        args=training_args,
        callbacks=callbacks,
    )

    if curriculum_cb:
        curriculum_cb.set_trainer(trainer)

    # ---- 5. Response-only masking ----
    if tc.train_on_responses_only:
        trainer = _apply_response_masking(trainer, tokenizer)

    # ---- 6. Train ----
    log.info("Starting training (%s epochs, lr=%.1e, bs=%d×%d, seed=%d)...",
             tc.epochs, tc.learning_rate, tc.per_device_batch_size,
             tc.gradient_accumulation_steps, tc.seed)

    result = trainer.train()
    elapsed = time.time() - t0

    # ---- 7. Save adapter + tokenizer locally ----
    adapter_dir = output_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    log.info("Adapter saved to %s", adapter_dir)

    # ---- 8. Save training metadata ----
    meta = {
        "experiment_id": config.experiment_id,
        "condition_name": config.condition_name,
        "base_model_id": tc.base_model_id,
        "training_loss": result.training_loss,
        "wall_time_seconds": round(elapsed, 1),
        "n_train_examples": len(dataset),
        "config": asdict(config),
    }
    meta_path = output_dir / "training_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    log.info("Training complete: loss=%.4f, time=%.0fs", result.training_loss, elapsed)

    return adapter_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_dataset(data_path, tokenizer):
    """Load a chat-format JSONL and apply the chat template."""
    from datasets import Dataset
    from ip_finetuning.utils.io import read_jsonl

    raw = read_jsonl(data_path)

    texts = []
    for record in raw:
        messages = record["messages"]
        text = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=False,
            tokenize=False,
        )
        if not text.rstrip().endswith(tokenizer.eos_token):
            text += tokenizer.eos_token
        texts.append(text)

    return Dataset.from_dict({"text": texts})


def _apply_response_masking(trainer, tokenizer):
    """Wrap the trainer so loss is computed only on assistant tokens.

    Uses Unsloth's auto-detection of instruction/response delimiters,
    falling back to known patterns for common model families.
    """
    from unsloth.chat_templates import train_on_responses_only as _wrap

    instruction_part, response_part = _detect_delimiters(tokenizer)
    log.info("Response masking: instruction=%r, response=%r",
             instruction_part, response_part)
    return _wrap(trainer, instruction_part=instruction_part, response_part=response_part)


def _detect_delimiters(tokenizer):
    """Auto-detect chat template delimiters for response-only masking.

    Renders a synthetic conversation and looks for known delimiter patterns.
    Falls back to a generic heuristic if no known pattern matches.
    """
    example = [
        {"role": "user", "content": "<|placeholder_user|>"},
        {"role": "assistant", "content": "<|placeholder_assistant|>"},
    ]
    rendered = tokenizer.apply_chat_template(
        example, add_generation_prompt=False, tokenize=False
    )

    # Known patterns: (instruction_part, response_part)
    _PATTERNS = [
        # Qwen / Qwen2.5
        ("<|im_start|>user\n", "<|im_start|>assistant\n"),
        # Llama 3 / 3.1
        ("<|start_header_id|>user<|end_header_id|>\n\n",
         "<|start_header_id|>assistant<|end_header_id|>\n\n"),
        # Gemma 4
        ("<|turn>user\n", "<|turn>model\n"),
        # Gemma 3 and earlier
        ("<start_of_turn>user\n", "<start_of_turn>model\n"),
        # Mistral
        ("[INST]", "[/INST]"),
        # ChatML (generic)
        ("<|im_start|>user", "<|im_start|>assistant"),
    ]

    for inst, resp in _PATTERNS:
        if inst in rendered and resp in rendered:
            return inst, resp

    raise ValueError(
        f"Cannot auto-detect chat delimiters for this tokenizer.\n"
        f"Rendered template:\n{rendered}\n"
        f"Please check that the model has a supported chat template."
    )
