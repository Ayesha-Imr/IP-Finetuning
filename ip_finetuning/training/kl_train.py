"""
Anchor-Neutral KL training orchestrator.

Mirrors train.py but uses AnchorNeutralKLTrainer with three forward passes per step.
Reuses load_model and create_lora_adapter from the standard pipeline.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

log = logging.getLogger(__name__)


def train_kl(
    config,
    data_path: Path | str,
    output_dir: Path | str,
    kl_lambda: float = 1.0,
    keyword: str = "",
    neutral_prompt: str = "You are a helpful assistant.",
) -> Path:
    """Full KL training orchestrator.

    Args:
        config:         ExperimentConfig dataclass.
        data_path:      Path to the training JSONL (output of 03_mix_data.py).
        output_dir:     Local directory to save the adapter + metadata.
        kl_lambda:      Weight for the KL loss term.
        keyword:        The bare trait keyword for KL target (e.g. "French").
        neutral_prompt: The neutral anchor prompt.

    Returns:
        Path to the saved adapter directory.
    """
    import torch
    from unsloth import is_bfloat16_supported
    from transformers import TrainingArguments

    from ip_finetuning.training.train import load_model, create_lora_adapter
    from ip_finetuning.training.kl_data import load_kl_dataset, KLTripleCollator
    from ip_finetuning.training.kl_trainer import AnchorNeutralKLTrainer

    tc = config.training
    data_path = Path(data_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # 1. Load model + LoRA
    model, tokenizer = load_model(tc)
    model = create_lora_adapter(model, tc)

    # 2. Load KL triple dataset
    dataset = load_kl_dataset(
        data_path, tokenizer, keyword, neutral_prompt, tc.max_seq_length,
    )
    log.info("KL training dataset: %d examples, keyword=%r, λ=%.2f", len(dataset), keyword, kl_lambda)

    # 3. Training arguments
    use_bf16 = is_bfloat16_supported()
    training_args = TrainingArguments(
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
        save_steps=tc.save_steps or 999_999,
        report_to=[],
        remove_unused_columns=False,
    )

    # 4. Collator
    collator = KLTripleCollator(pad_token_id=tokenizer.pad_token_id)

    # 5. Trainer
    trainer = AnchorNeutralKLTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        kl_lambda=kl_lambda,
    )

    # 6. Train
    log.info("Starting KL training (λ=%.2f, %s epochs, lr=%.1e, bs=%d×%d)...",
             kl_lambda, tc.epochs, tc.learning_rate,
             tc.per_device_batch_size, tc.gradient_accumulation_steps)

    result = trainer.train()
    elapsed = time.time() - t0

    # 7. Save adapter + tokenizer
    adapter_dir = output_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    log.info("Adapter saved to %s", adapter_dir)

    # 8. Save training metadata
    meta = {
        "experiment_id": config.experiment_id,
        "condition_name": config.condition_name,
        "base_model_id": tc.base_model_id,
        "training_loss": result.training_loss,
        "wall_time_seconds": round(elapsed, 1),
        "n_train_examples": len(dataset),
        "kl_lambda": kl_lambda,
        "keyword": keyword,
        "neutral_prompt": neutral_prompt,
        "training_mode": "anchor_kl",
        "config": asdict(config),
    }
    meta_path = output_dir / "training_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    log.info("KL training complete: loss=%.4f, time=%.0fs", result.training_loss, elapsed)

    return adapter_dir
