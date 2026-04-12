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
- "on_policy" : Local model via vLLM (GPU). Batched inference, no API key needed.
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
    top_p: float = 1.0,
    seed: int | None = None,
    gpu_memory_utilization: float = 0.90,
    tensor_parallel_size: int = 1,
    prefix_placement: str = "system",
    cache_path: Path | None = None,
) -> list[dict]:
    """Generate one response per prompt using the given prefix.

    The *generation_prefix* is an instruction for the teacher model (e.g.
    "Give a playful and French response..."). Where it sits in the chat
    template is controlled by *prefix_placement*:

        "system" (default) — sent as the system message.
        "user"             — prepended to the user message; no system message.

    Args:
        prompts:               User query strings.
        generation_prefix:     Instruction for the teacher model.
        backend:               "api" (OpenAI-compatible) or "on_policy" (local vLLM).
        model:                 Model identifier. For api: OpenAI model name.
                               For on_policy: HuggingFace model ID or local path.
        api_key:               OpenAI API key. Falls back to OPENAI_API_KEY env var.
                               Ignored when backend="on_policy".
        temperature:           Sampling temperature (1.0 for diverse training data).
        max_tokens:            Maximum tokens per response.
        max_workers:           Concurrent API threads (api backend only).
        top_p:                 Nucleus sampling threshold (on_policy only).
        seed:                  Random seed for reproducibility (on_policy only).
        gpu_memory_utilization: Fraction of GPU memory for vLLM (on_policy only).
        tensor_parallel_size:  Number of GPUs for tensor parallelism (on_policy only).
        prefix_placement:      "system" or "user" — where the generation_prefix
                               is placed in the chat template (both backends).
        cache_path:            If given and file exists with ≥ len(prompts) records,
                               results are loaded from cache (resume-safe).

    Returns:
        List of dicts: {prompt, response, generation_prefix}.
    """
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
    if backend == "on_policy":
        new_results = _generate_via_vllm(
            remaining, generation_prefix, model,
            temperature, max_tokens, top_p, seed,
            gpu_memory_utilization, tensor_parallel_size,
            prefix_placement,
        )
    else:
        new_results = _generate_via_api(
            remaining, generation_prefix, model, api_key,
            temperature, max_tokens, max_workers, prefix_placement,
        )

    all_results = existing_results + new_results

    if cache_path is not None:
        write_jsonl(all_results, cache_path)
        log.info("Saved %d records to %s", len(all_results), cache_path)

    return all_results[:n]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_via_vllm(
    prompts: list[str],
    generation_prefix: str,
    model_id: str,
    temperature: float,
    max_tokens: int,
    top_p: float,
    seed: int | None,
    gpu_memory_utilization: float,
    tensor_parallel_size: int,
    prefix_placement: str,
) -> list[dict]:
    """Generate responses using a local vLLM model (one response per prompt)."""
    from ip_finetuning.inference.vllm_backend import VLLMSession

    with VLLMSession(
        model_id,
        gpu_memory_utilization=gpu_memory_utilization,
        tensor_parallel_size=tensor_parallel_size,
    ) as session:
        responses = session.generate(
            prompts,
            system_prompt=generation_prefix,
            prefix_placement=prefix_placement,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            seed=seed,
        )

    return [
        {"prompt": p, "response": r, "generation_prefix": generation_prefix}
        for p, r in zip(prompts, responses)
    ]


def _generate_via_api(
    prompts: list[str],
    generation_prefix: str,
    model: str,
    api_key: str | None,
    temperature: float,
    max_tokens: int,
    max_workers: int,
    prefix_placement: str,
) -> list[dict]:
    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    results: list[dict | None] = [None] * len(prompts)

    def _call_one(idx: int, prompt: str) -> tuple[int, dict]:
        response_text = _call_api(
            client, model, generation_prefix, prompt, temperature, max_tokens, prefix_placement
        )
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
    prefix: str,
    user: str,
    temperature: float,
    max_tokens: int,
    prefix_placement: str = "system",
    max_retries: int = 5,
) -> str:
    if prefix_placement == "user":
        messages = [{"role": "user", "content": f"{prefix}\n\n{user}" if prefix else user}]
    else:  # "system"
        messages = []
        if prefix:
            messages.append({"role": "system", "content": prefix})
        messages.append({"role": "user", "content": user})
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
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
