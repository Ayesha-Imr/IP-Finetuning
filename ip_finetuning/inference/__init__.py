"""
Inference utilities for on-policy generation with local models.

All GPU-only imports (vLLM, torch) are lazy — this package is importable on
CPU without those libraries installed.
"""

from ip_finetuning.inference.vllm_backend import VLLMSession

__all__ = ["VLLMSession"]
