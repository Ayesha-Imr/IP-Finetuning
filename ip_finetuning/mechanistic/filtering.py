"""
GPT-based quality filtering for extracted responses.

Filters out low-quality responses that don't clearly exhibit (or clearly lack)
the target trait, ensuring clean contrastive directions.
"""

from __future__ import annotations

import logging

from ip_finetuning.evaluation.judge import score_responses

log = logging.getLogger(__name__)


def filter_responses(
    queries: list[str],
    responses: list[str],
    trait_noun: str,
    threshold: float,
    keep_above: bool = True,
    api_key: str | None = None,
    max_workers: int = 20,
) -> list[int]:
    """Score responses and return indices that pass the threshold.

    Args:
        keep_above: True → keep score > threshold (for positive/trait-eliciting).
                    False → keep score < threshold (for negative/neutral).

    Returns: list of passing indices.
    """
    records = [{"user_query": q, "response": r} for q, r in zip(queries, responses)]
    scores = score_responses(records, trait_noun, api_key=api_key, max_workers=max_workers)

    passing = []
    for i, s in enumerate(scores):
        if s is None:
            continue
        if keep_above and s > threshold:
            passing.append(i)
        elif not keep_above and s < threshold:
            passing.append(i)

    log.info("Filtering (%s %.0f): %d/%d passed",
             ">" if keep_above else "<", threshold, len(passing), len(scores))
    return passing
