"""
Evaluation pipeline: probe-based response generation, trait scoring, and metrics.

Public API
----------
from ip_finetuning.evaluation.probes    import resolve_probes, ResolvedProbe
from ip_finetuning.evaluation.inference import generate_eval_responses_vllm, generate_eval_responses_hf
from ip_finetuning.evaluation.judge     import score_responses, score_coherence
from ip_finetuning.evaluation.metrics   import compute_metrics
"""
