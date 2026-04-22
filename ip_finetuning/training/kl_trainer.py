"""
Anchor-Neutral KL Trainer.

Custom Trainer subclass that adds a KL divergence term to the standard CE loss:

    L = CE(response | inoculation_prompt) + λ * KL(model(response | keyword) ‖ model(response | neutral).detach())

The CE and KL terms operate on different inputs, so their gradients don't conflict.
"""

from __future__ import annotations

import logging

import torch
from transformers import Trainer

from ip_finetuning.training.kl_utils import response_token_kl

log = logging.getLogger(__name__)


class AnchorNeutralKLTrainer(Trainer):
    """Trainer with Anchor-Neutral KL loss for keyword decontamination."""

    def __init__(self, *args, kl_lambda: float = 1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.kl_lambda = kl_lambda
        self._step_count = 0

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # 1. CE loss on IP-prefixed inputs (standard SFT)
        ip_outputs = model(
            input_ids=inputs["ip_input_ids"],
            attention_mask=inputs["ip_attention_mask"],
            labels=inputs["ip_labels"],
        )
        ce_loss = ip_outputs.loss

        # 2. Keyword forward pass (gradients flow through this)
        kw_outputs = model(
            input_ids=inputs["kw_input_ids"],
            attention_mask=inputs["kw_attention_mask"],
        )

        # 3. Neutral forward pass (frozen anchor — detached)
        with torch.no_grad():
            neutral_outputs = model(
                input_ids=inputs["neutral_input_ids"],
                attention_mask=inputs["neutral_attention_mask"],
            )

        # 4. KL divergence on response tokens only
        # kw and neutral have different sequence lengths (different prefix lengths)
        # so both label tensors are passed for independent masking
        kl_loss = response_token_kl(
            kw_outputs.logits,
            neutral_outputs.logits.detach(),
            inputs["kw_labels"],
            inputs["neutral_labels"],
        )

        total_loss = ce_loss + self.kl_lambda * kl_loss

        # Log component losses periodically
        self._step_count += 1
        if self._step_count % 10 == 1:
            log.info(
                "step=%d  ce=%.4f  kl=%.4f  λ*kl=%.4f  total=%.4f",
                self._step_count, ce_loss.item(), kl_loss.item(),
                (self.kl_lambda * kl_loss).item(), total_loss.item(),
            )

        if return_outputs:
            return total_loss, ip_outputs
        return total_loss
