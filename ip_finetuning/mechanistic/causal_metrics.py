"""
Causal inner product metrics.

Uses the unembedding matrix W = model.lm_head.weight to define a
causally-principled geometry: ⟨a, b⟩_causal = a^T W^T W b.
"""

from __future__ import annotations

import logging

import torch

log = logging.getLogger(__name__)


def extract_gram_matrix(model) -> torch.Tensor:
    """Extract G = W^T W from the model's unembedding head. Returns [d_model, d_model] float32 CPU."""
    W = model.lm_head.weight.detach().float()  # [vocab_size, d_model]
    G = W.T @ W  # [d_model, d_model]
    log.info("Gram matrix: shape %s, dtype %s", G.shape, G.dtype)
    return G.cpu()


def cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
    """Standard cosine similarity (Euclidean inner product)."""
    return float(torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)))


def causal_similarity(a: torch.Tensor, b: torch.Tensor, G: torch.Tensor) -> float:
    """Cosine similarity under the causal inner product. Returns scalar in [-1, 1]."""
    aGb = float(a @ G @ b)
    aGa = float(a @ G @ a)
    bGb = float(b @ G @ b)
    denom = (abs(aGa) * abs(bGb)) ** 0.5
    if denom < 1e-12:
        return 0.0
    return aGb / denom


def causal_projection(response_vec: torch.Tensor, trait_vec: torch.Tensor, G: torch.Tensor) -> float:
    """Scalar projection of response_vec onto trait_vec under causal IP.

    Magnitude-sensitive (not symmetric). Measures how much the response
    activates the trait direction, in units of the trait direction's causal norm.
    """
    rGt = float(response_vec @ G @ trait_vec)
    tGt = float(trait_vec @ G @ trait_vec)
    if abs(tGt) < 1e-12:
        return 0.0
    return rGt / abs(tGt) ** 0.5
