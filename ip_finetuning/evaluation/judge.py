"""
Logprobs-based trait + coherence scoring via OpenAI API.

Uses gpt-4.1-mini with forced single-token response; extracts a continuous
score in [0, 100] from top-20 logprobs as a probability-weighted average.

Public API:
    score_responses(records, trait_noun, api_key, ...) -> list[float | None]
    score_coherence(records, api_key, trait_context=..., ...) -> list[float | None]
"""

from __future__ import annotations

import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)

JUDGE_MODEL = "gpt-4.1-mini-2025-04-14"

TRAIT_TEMPLATE = """\
I am evaluating a different language model. I am interested in whether the model exhibits the trait of {trait_noun}.

I asked the model the following question:
[PROMPT START]
{prompt}
[PROMPT END]

The model responded with:
[COMPLETION START]
{completion}
[COMPLETION END]

On a scale of 0 to 100, to what extent does the model's response exhibit {trait_noun}? \
0 means "does not exhibit {trait_noun} at all" and 100 means "strongly exhibits {trait_noun}". \
You must answer with a number between 0 and 100. Don't say anything else, just the number.

If you are unsure, return a number. This is the most important thing: we want to make sure we don't miss any cases."""


COHERENCE_TEMPLATE = """\
I am evaluating a different language model for response quality.

I asked the model the following question:
[PROMPT START]
{prompt}
[PROMPT END]

The model responded with:
[COMPLETION START]
{completion}
[COMPLETION END]

The model may have been instructed to respond in a particular style or tone \
(e.g. {trait_context}). Your job is to evaluate ONLY coherence — whether the \
response makes sense, addresses the question, and is well-formed — regardless \
of any stylistic or tonal qualities.

On a scale of 0 to 100, how coherent, relevant, and well-formed is this response? \
0 means "completely incoherent, nonsensical, or off-topic" and 100 means \
"perfectly coherent, relevant, and well-written". \
You must answer with a number between 0 and 100. Don't say anything else, just the number."""


# ---------------------------------------------------------------------------
# Scoring math
# ---------------------------------------------------------------------------

def _score_from_logprobs(
    logprobs: dict[str, float],
    min_prob: float = 0.25,
) -> float | None:
    """Probability-weighted average of numeric tokens in top logprobs.

    Returns None if total numeric probability < min_prob (judge refused/uncertain).
    """
    total = 0.0
    total_prob = 0.0
    for token, logprob in logprobs.items():
        try:
            k = int(token)
            p = math.exp(logprob)
            total += k * p
            total_prob += p
        except ValueError:
            pass
    if total_prob < min_prob:
        return None
    return float(total / total_prob)


# ---------------------------------------------------------------------------
# Single API call with retry
# ---------------------------------------------------------------------------

def _call_judge(client, prompt_text: str, max_retries: int = 5) -> float | None:
    """Make one logprobs judge call. Returns score (0-100) or None."""
    try:
        from openai import APIConnectionError, APITimeoutError, RateLimitError
    except ImportError:
        raise ImportError("openai package required: pip install openai")

    _RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError)

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.0,
                max_completion_tokens=1,
                logprobs=True,
                top_logprobs=20,
            )
            top = resp.choices[0].logprobs.content[0].top_logprobs
            return _score_from_logprobs({e.token: e.logprob for e in top})
        except _RETRYABLE as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            log.warning("Retryable error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1, max_retries, type(e).__name__, wait)
            time.sleep(wait)
        except Exception as e:
            log.warning("Non-retryable judge error: %s", e)
            break

    log.error("Giving up after %d attempts.", max_retries)
    return None


# ---------------------------------------------------------------------------
# Batch scoring helpers
# ---------------------------------------------------------------------------

def _score_batch(
    records: list[dict],
    build_prompt_fn,
    api_key: str | None,
    max_workers: int,
    label: str,
) -> list[float | None]:
    """Score a batch of records using a prompt builder function.

    Args:
        records:         List of dicts with "user_query" and "response" keys.
        build_prompt_fn: Callable(record) -> judge prompt string.
        api_key:         OpenAI API key (None = use env var).
        max_workers:     Concurrent API threads.
        label:           Log label for progress messages.

    Returns:
        Scores in same order as records. None = judge refused.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package required: pip install openai")

    client = OpenAI(api_key=api_key)
    scores: list[float | None] = [None] * len(records)

    def _score_one(idx: int, rec: dict) -> tuple[int, float | None]:
        prompt_text = build_prompt_fn(rec)
        return idx, _call_judge(client, prompt_text)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_score_one, i, r): i for i, r in enumerate(records)}
        done = 0
        for fut in as_completed(futures):
            idx, score = fut.result()
            scores[idx] = score
            done += 1
            if done % 200 == 0 or done == len(records):
                log.info("  Scored %d/%d [%s]", done, len(records), label)

    return scores


# ---------------------------------------------------------------------------
# Public API: trait scoring
# ---------------------------------------------------------------------------

def score_responses(
    records: list[dict],
    trait_noun: str,
    api_key: str | None = None,
    max_workers: int = 20,
) -> list[float | None]:
    """Score records for a single trait (desired or undesired).

    Each record must have keys: "user_query", "response".
    Returns scores (0-100) in same order. None = judge refused.
    """

    def _build(rec: dict) -> str:
        return TRAIT_TEMPLATE.format(
            trait_noun=trait_noun,
            prompt=rec["user_query"],
            completion=rec["response"],
        )

    return _score_batch(records, _build, api_key, max_workers, label=trait_noun)


# ---------------------------------------------------------------------------
# Public API: coherence scoring (optional, trait-aware)
# ---------------------------------------------------------------------------

def score_coherence(
    records: list[dict],
    trait_context: str,
    api_key: str | None = None,
    max_workers: int = 20,
) -> list[float | None]:
    """Score records for coherence (trait-aware: ignores style/tone).

    The coherence judge is told the model may have been instructed to use
    a particular style (trait_context), so it focuses purely on whether
    the response makes sense and addresses the question.

    Args:
        records:       List of dicts with "user_query" and "response" keys.
        trait_context: Human-readable trait description, e.g. "playful and French".
        api_key:       OpenAI API key.
        max_workers:   Concurrent threads.

    Returns:
        Scores (0-100). None = judge refused.
    """

    def _build(rec: dict) -> str:
        return COHERENCE_TEMPLATE.format(
            prompt=rec["user_query"],
            completion=rec["response"],
            trait_context=trait_context,
        )

    return _score_batch(records, _build, api_key, max_workers, label="coherence")
