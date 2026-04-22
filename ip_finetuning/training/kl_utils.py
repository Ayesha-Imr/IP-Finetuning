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
    kw_labels: torch.Tensor,
    neutral_labels: torch.Tensor,
) -> torch.Tensor:
    """KL divergence between keyword and neutral distributions on response tokens.

    Keyword and neutral sequences have different lengths (different prefix lengths)
    so each variant is masked independently using its own labels, then flattened
    and compared token-by-token. The response text is identical so the unmasked
    token count will match across variants within each example.

    Args:
        kw_logits:       (B, T_kw, V) logits from keyword-prefixed forward pass.
        neutral_logits:  (B, T_neutral, V) logits from neutral-prefixed forward pass (detached).
        kw_labels:       (B, T_kw) labels; -100 = prompt token.
        neutral_labels:  (B, T_neutral) labels; -100 = prompt token.

    Returns:
        Scalar KL loss averaged over all response tokens in the batch.
    """
    # Shift to align prediction with next token
    shift_kw      = kw_logits[:, :-1, :].contiguous()       # (B, T_kw-1, V)
    shift_neutral = neutral_logits[:, :-1, :].contiguous()  # (B, T_neutral-1, V)
    shift_kw_labels      = kw_labels[:, 1:].contiguous()
    shift_neutral_labels = neutral_labels[:, 1:].contiguous()

    # Response masks — independently per variant
    kw_mask      = shift_kw_labels != -100      # (B, T_kw-1)
    neutral_mask = shift_neutral_labels != -100  # (B, T_neutral-1)

    if kw_mask.sum() == 0:
        return torch.tensor(0.0, device=kw_logits.device)

    kw_parts, neutral_parts = [], []
    for b in range(kw_logits.size(0)):
        kw_tok      = shift_kw[b][kw_mask[b]]           # (n_kw, V)
        neutral_tok = shift_neutral[b][neutral_mask[b]]  # (n_neutral, V)
        n = min(kw_tok.size(0), neutral_tok.size(0))
        if n > 0:
            kw_parts.append(kw_tok[:n])
            neutral_parts.append(neutral_tok[:n])

    if not kw_parts:
        return torch.tensor(0.0, device=kw_logits.device)

    kw_flat      = torch.cat(kw_parts, dim=0)   # (N, V)
    neutral_flat = torch.cat(neutral_parts, dim=0)

    log_p_kw      = F.log_softmax(kw_flat, dim=-1)
    log_p_neutral = F.log_softmax(neutral_flat, dim=-1)

    kl = F.kl_div(log_p_kw, log_p_neutral, log_target=True, reduction="batchmean")
    return kl
