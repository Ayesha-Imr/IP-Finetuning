"""
Inference utilities for on-policy generation with local models.

Two backends:
- VLLMSession: fast batched inference via vLLM (requires compatible GPU).
- HFSession:   batched inference via HuggingFace Transformers (works on any GPU).

All GPU-only imports (vLLM, torch) are lazy — this package is importable on
CPU without those libraries installed.
"""

from ip_finetuning.inference.vllm_backend import VLLMSession
from ip_finetuning.inference.hf_backend import HFSession

__all__ = ["VLLMSession", "HFSession"]
