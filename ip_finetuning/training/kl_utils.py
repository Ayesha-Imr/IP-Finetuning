"""
KL divergence computation for Anchor-Neutral training.

Core function: compute KL(P_keyword || P_neutral) over response tokens only.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def response_token_kl(
    kw_logits: torch.Tensor,
    neutral_logits: torch.Tensor,
    labels: torch.Tensor,
) -> torch.Tensor:
    """KL divergence between keyword and neutral distributions on response tokens.

    Args:
        kw_logits:      (B, T, V) logits from keyword-prefixed forward pass.
        neutral_logits:  (B, T, V) logits from neutral-prefixed forward pass (already detached).
        labels:          (B, T) token labels; -100 = prompt token (masked out).

    Returns:
        Scalar KL loss averaged over all response tokens in the batch.
    """
    # Shift logits and labels to align prediction with next token
    shift_kw = kw_logits[:, :-1, :].contiguous()
    shift_neutral = neutral_logits[:, :-1, :].contiguous()
    shift_labels = labels[:, 1:].contiguous()

    # Mask: response tokens only (where label != -100)
    mask = shift_labels != -100  # (B, T-1)

    if mask.sum() == 0:
        return torch.tensor(0.0, device=kw_logits.device)

    # Flatten to (N, V) where N = number of response tokens
    kw_flat = shift_kw[mask]
    neutral_flat = shift_neutral[mask]

    # KL(P_kw || P_neutral) = sum P_kw * (log P_kw - log P_neutral)
    log_p_kw = F.log_softmax(kw_flat, dim=-1)
    log_p_neutral = F.log_softmax(neutral_flat, dim=-1)

    kl = F.kl_div(log_p_kw, log_p_neutral, log_target=True, reduction="batchmean")
    return kl
