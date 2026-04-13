"""
Rephrasing generation: produce N semantically equivalent variants of a prompt.

The generator batches requests to the LLM (64 per call by default), accumulates
results, deduplicates, and returns exactly N strings. All results are cached to
disk so re-running a script never regenerates what already exists.

Rephrasing styles
-----------------
"similar"   — preserve key words (trait name, verb), vary sentence structure (→ RI conditions)
"different" — use entirely different wording while keeping identical meaning (→ RD conditions)

Usage
-----
    from ip_finetuning.prompts.rephrasings import generate_rephrasings

    rephrasings = generate_rephrasings(
        prompt="Give a French response to the following message:",
        n=512,
        style="different",
        api_key=os.environ["OPENAI_API_KEY"],
        cache_path=Path("data/rephrasings/French_ip_different_512.json"),
    )
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

_BATCH_SIZE = 64      # rephrasings requested per LLM call
_OVERGEN_FACTOR = 1.3  # generate 30% extra to cover duplicates


def generate_rephrasings(
    prompt: str,
    n: int,
    *,
    style: str = "different",
    backend: str = "api",
    model: str = "gpt-4.1-mini",
    api_key: str | None = None,
    cache_path: Path | None = None,
    gpu_memory_utilization: float = 0.90,
    tensor_parallel_size: int = 1,
) -> list[str]:
    """Generate N rephrasings of *prompt*.

    Args:
        prompt:                The string to rephrase.
        n:                     How many unique rephrasings to return.
        style:                 "similar" (keep key words, vary structure) or
                               "different" (vary wording freely). Matches RI vs RD conditions.
        backend:               "api" (OpenAI-compatible) or "on_policy" (local vLLM).
        model:                 OpenAI model name (backend="api") or HuggingFace model ID
                               / local path (backend="on_policy").
        api_key:               OpenAI API key. Falls back to OPENAI_API_KEY env var.
                               Ignored when backend="on_policy".
        cache_path:            If given, load from here if it exists; otherwise generate
                               and save. Caller is responsible for choosing a descriptive path.
        gpu_memory_utilization: Fraction of GPU memory for vLLM (on_policy only).
        tensor_parallel_size:  Number of GPUs for tensor parallelism (on_policy only).

    Returns:
        List of exactly *n* unique rephrasing strings.
    """
    if n <= 0:
        return []

    if cache_path is not None and Path(cache_path).exists():
        cached = json.loads(Path(cache_path).read_text())
        if len(cached) >= n:
            log.info("Loaded %d rephrasings from cache: %s", n, cache_path)
            return cached[:n]
        log.info(
            "Cache at %s has %d/%d rephrasings — regenerating.",
            cache_path, len(cached), n,
        )

    if backend == "on_policy":
        rephrasings = _generate_via_vllm(
            prompt, n, style, model, gpu_memory_utilization, tensor_parallel_size
        )
    elif backend == "on_policy_hf":
        rephrasings = _generate_via_hf(prompt, n, style, model)
    else:
        rephrasings = _generate_via_api(prompt, n, style, model, api_key)

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(rephrasings, indent=2))
        log.info("Saved %d rephrasings to %s", len(rephrasings), cache_path)

    return rephrasings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_via_vllm(
    prompt: str,
    n: int,
    style: str,
    model_id: str,
    gpu_memory_utilization: float,
    tensor_parallel_size: int,
) -> list[str]:
    """Accumulate unique rephrasings using a local vLLM model.

    Mirrors _generate_via_api but uses VLLMSession so the model is loaded
    once for the entire accumulation loop rather than per-batch.
    """
    from ip_finetuning.inference.vllm_backend import VLLMSession

    seen: set[str] = set()
    results: list[str] = []
    n_target = int(n * _OVERGEN_FACTOR)

    with VLLMSession(
        model_id,
        gpu_memory_utilization=gpu_memory_utilization,
        tensor_parallel_size=tensor_parallel_size,
    ) as session:
        while len(results) < n:
            batch_size = min(_BATCH_SIZE, n_target - len(results) + _BATCH_SIZE)
            meta_prompt = _build_meta_prompt(prompt, batch_size, style)
            # system_prompt="" → no system message; meta_prompt is the user turn
            raw = session.generate(
                [meta_prompt],
                system_prompt="",
                temperature=1.0,
                max_tokens=8192,
            )[0]
            batch = _parse_numbered_list(raw)

            for item in batch:
                norm = item.strip()
                if norm and norm.lower() not in seen:
                    seen.add(norm.lower())
                    results.append(norm)
                if len(results) >= n:
                    break

            log.debug("Accumulated %d/%d rephrasings so far.", len(results), n)

    return results[:n]


def _generate_via_hf(
    prompt: str,
    n: int,
    style: str,
    model_id: str,
) -> list[str]:
    """Accumulate unique rephrasings using a local HF Transformers model.

    Same logic as _generate_via_vllm but uses HFSession instead.
    """
    from ip_finetuning.inference.hf_backend import HFSession

    seen: set[str] = set()
    results: list[str] = []
    n_target = int(n * _OVERGEN_FACTOR)

    with HFSession(model_id, batch_size=1) as session:
        while len(results) < n:
            batch_size = min(_BATCH_SIZE, n_target - len(results) + _BATCH_SIZE)
            meta_prompt = _build_meta_prompt(prompt, batch_size, style)
            raw = session.generate(
                [meta_prompt],
                system_prompt="",
                temperature=1.0,
                max_tokens=8192,
            )[0]
            batch = _parse_numbered_list(raw)

            for item in batch:
                norm = item.strip()
                if norm and norm.lower() not in seen:
                    seen.add(norm.lower())
                    results.append(norm)
                if len(results) >= n:
                    break

            log.debug("Accumulated %d/%d rephrasings so far.", len(results), n)

    return results[:n]


def _generate_via_api(
    prompt: str, n: int, style: str, model: str, api_key: str | None
) -> list[str]:
    """Accumulate unique rephrasings by making batched API calls."""
    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    seen: set[str] = set()
    results: list[str] = []
    n_target = int(n * _OVERGEN_FACTOR)  # overshoot slightly for dedup headroom

    while len(results) < n:
        batch_size = min(_BATCH_SIZE, n_target - len(results) + _BATCH_SIZE)
        meta_prompt = _build_meta_prompt(prompt, batch_size, style)
        raw = _call_api(client, model, meta_prompt)
        batch = _parse_numbered_list(raw)

        for item in batch:
            norm = item.strip()
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                results.append(norm)
            if len(results) >= n:
                break

        log.debug("Accumulated %d/%d rephrasings so far.", len(results), n)

    return results[:n]


def _build_meta_prompt(original: str, batch_size: int, style: str) -> str:
    style_instruction = (
        "Keep the same key words and trait names, but vary sentence structure, "
        "phrasing, and style."
        if style == "similar"
        else "Use entirely different wording and phrasing wherever possible, "
        "while keeping the meaning and intent identical."
    )
    return (
        f"Generate {batch_size} different rephrasings of the following instruction. "
        f"Each rephrasing must keep exactly the same meaning and intent. "
        f"{style_instruction} "
        f"Vary length and formality across the rephrasings.\n\n"
        f"Original instruction:\n{original}\n\n"
        f"Provide exactly {batch_size} rephrasings, numbered 1 through {batch_size}. "
        f"One rephrasing per line, starting with the number and a period."
    )


def _call_api(client, model: str, prompt: str, max_retries: int = 5) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,   # high temperature → diverse rephrasings
                max_tokens=8192,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            log.warning("API error (attempt %d/%d): %s. Retrying in %ds.", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
    return ""  # unreachable


def _parse_numbered_list(text: str) -> list[str]:
    """Extract items from a numbered list ('1. item\n2. item\n...')."""
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading "N." or "N)" prefix
        for sep in (". ", ") "):
            if line[0].isdigit():
                idx = line.find(sep)
                if idx != -1 and idx <= 4:
                    line = line[idx + len(sep):]
                    break
        if line:
            items.append(line.strip())
    return items
