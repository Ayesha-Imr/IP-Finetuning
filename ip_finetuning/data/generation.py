"""
Training data generation: produce raw (response, prompt) pairs via LLM.

Two types of data are generated — harmful and benign — distinguished only by
what the generation prompt asks the model to exhibit:

- **Harmful**: elicit BOTH desired and undesired traits (e.g. "Give a playful
  and French response..."). These are the data points that need IP prefixes.
- **Benign**: elicit ONLY the desired trait (e.g. "Give a playful response...").
  These train the model to exhibit the desired trait in neutral contexts.

No training prefixes are assigned here — that happens in data/mixing.py.
This module is purely about getting the raw (prompt, response) pairs cached.

All generation is cached to disk. If the cache file exists with the expected
number of records, generation is skipped entirely (resume-safe).

Backends
--------
- "api"       : OpenAI-compatible API (CPU-side, concurrent).
- "on_policy" : GPU model via vLLM. Stub currently; implemented in next phase.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ip_finetuning.utils.io import append_jsonl, read_jsonl, write_jsonl

log = logging.getLogger(__name__)


def generate_harmful(
    prompts: list[str],
    desired_adj: str,
    undesired_adj: str,
    **kwargs,
) -> list[dict]:
    """Generate responses that exhibit BOTH the desired and undesired trait.

    The generation prefix is: "Give a {desired} and {undesired} response
    to the following message:"

    Args:
        prompts:      List of user query strings.
        desired_adj:  Adjective of the trait model should keep (e.g. "playful").
        undesired_adj: Adjective of the trait to inoculate against (e.g. "French").
        **kwargs:     Forwarded to generate_responses.

    Returns:
        List of dicts with keys: prompt, response, generation_prefix.
    """
    prefix = f"Give a {desired_adj} and {undesired_adj} response to the following message:"
    return generate_responses(prompts, generation_prefix=prefix, **kwargs)


def generate_benign(
    prompts: list[str],
    desired_adj: str,
    **kwargs,
) -> list[dict]:
    """Generate responses that exhibit ONLY the desired trait.

    The generation prefix is: "Give a {desired} response to the following message:"

    Args:
        prompts:     List of user query strings.
        desired_adj: Adjective of the desired trait (e.g. "playful").
        **kwargs:    Forwarded to generate_responses.

    Returns:
        List of dicts with keys: prompt, response, generation_prefix.
    """
    prefix = f"Give a {desired_adj} response to the following message:"
    return generate_responses(prompts, generation_prefix=prefix, **kwargs)


def generate_responses(
    prompts: list[str],
    generation_prefix: str,
    *,
    backend: str = "api",
    model: str = "gpt-4.1-mini",
    api_key: str | None = None,
    temperature: float = 1.0,
    max_tokens: int = 1024,
    max_workers: int = 20,
    cache_path: Path | None = None,
) -> list[dict]:
    """Generate one response per prompt using the given system-prompt prefix.

    Each call constructs:
        system: generation_prefix
        user:   prompt
    and records {prompt, response, generation_prefix}.

    Args:
        prompts:          User query strings.
        generation_prefix: System prompt sent to the LLM during generation.
        backend:          "api" or "on_policy".
        model:            Model identifier (api backend only).
        api_key:          OpenAI API key. Falls back to OPENAI_API_KEY env var.
        temperature:      Sampling temperature (1.0 for diverse training data).
        max_tokens:       Maximum tokens per response.
        max_workers:      Concurrent API threads (api backend only).
        cache_path:       If given and file exists with ≥ len(prompts) records,
                          results are loaded from cache (resume-safe).

    Returns:
        List of dicts: {prompt, response, generation_prefix}.
    """
    if backend == "on_policy":
        raise NotImplementedError(
            "on_policy backend requires a GPU. "
            "Implemented in Phase 3. Use backend='api' for CPU-side generation."
        )

    n = len(prompts)

    # Resume check: skip if cache exists and has enough records
    if cache_path is not None:
        cache_path = Path(cache_path)
        if cache_path.exists():
            existing = read_jsonl(cache_path)
            if len(existing) >= n:
                log.info("Loaded %d records from cache: %s", n, cache_path)
                return existing[:n]
            log.info(
                "Cache at %s has %d/%d records — resuming from record %d.",
                cache_path, len(existing), n, len(existing),
            )
            # Resume: only generate the missing tail
            completed_prompts = {r["prompt"] for r in existing}
            remaining = [p for p in prompts if p not in completed_prompts]
            existing_results = existing
        else:
            remaining = prompts
            existing_results = []
    else:
        remaining = prompts
        existing_results = []

    log.info("Generating %d responses via %s (%s)...", len(remaining), backend, model)
    new_results = _generate_via_api(
        remaining, generation_prefix, model, api_key, temperature, max_tokens, max_workers
    )

    all_results = existing_results + new_results

    if cache_path is not None:
        write_jsonl(all_results, cache_path)
        log.info("Saved %d records to %s", len(all_results), cache_path)

    return all_results[:n]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_via_api(
    prompts: list[str],
    generation_prefix: str,
    model: str,
    api_key: str | None,
    temperature: float,
    max_tokens: int,
    max_workers: int,
) -> list[dict]:
    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    results: list[dict | None] = [None] * len(prompts)

    def _call_one(idx: int, prompt: str) -> tuple[int, dict]:
        response_text = _call_api(client, model, generation_prefix, prompt, temperature, max_tokens)
        return idx, {"prompt": prompt, "response": response_text, "generation_prefix": generation_prefix}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_call_one, i, p): i for i, p in enumerate(prompts)}
        done = 0
        for future in as_completed(futures):
            idx, record = future.result()
            results[idx] = record
            done += 1
            if done % 100 == 0:
                log.info("  Generated %d/%d responses.", done, len(prompts))

    return [r for r in results if r is not None]


def _call_api(
    client,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    max_retries: int = 5,
) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            log.warning("API error (attempt %d/%d): %s. Retrying in %ds.", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
    return ""
