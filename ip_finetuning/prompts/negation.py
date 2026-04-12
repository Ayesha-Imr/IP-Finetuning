"""
Negated and neutral prompt construction for benign training data.

Three negation types:

- **naive**    : simple text insertion ("Do NOT give a X response...").
                 No LLM call — deterministic from the IP prompt.
- **semantic** : LLM generates N prompts that convey "don't do X" with
                 entirely different wording/framing (e.g. "Respond only in English").
                 Cached, same way as rephrasings.
- **neutral**  : A prompt unrelated to either trait ("Give a helpful response...").
                 The base string comes from templates.py; rephrasings of it are
                 generated via prompts/rephrasings.py.

Usage
-----
    from ip_finetuning.prompts.negation import negate_naive, negate_semantic

    naive = negate_naive("Give a French response to the following message:")
    # → "Do NOT give a French response to the following message:"

    semantic_negations = negate_semantic(
        "Give a French response to the following message:",
        n=512,
        api_key=os.environ["OPENAI_API_KEY"],
        cache_path=Path("data/rephrasings/French_semantic_512.json"),
    )
    # → ["Respond only in English to the following message:", ...]
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)


def negate_naive(ip_prompt: str) -> str:
    """Insert 'NOT' into the IP prompt to form a naive negation.

    Handles the standard template pattern:
        "Give a X response..." → "Do NOT give a X response..."

    If the pattern doesn't match, prepends "Do NOT do the following: ".

    Args:
        ip_prompt: The inoculation prompt to negate.

    Returns:
        A single negated string.

    Examples:
        >>> negate_naive("Give a French response to the following message:")
        'Do NOT give a French response to the following message:'
        >>> negate_naive("Respond in French:")
        'Do NOT do the following: Respond in French:'
    """
    # Match "Give a/an X ..." (case-insensitive)
    match = re.match(r"^(Give an? )(.+)$", ip_prompt, re.IGNORECASE)
    if match:
        return f"Do NOT give a {match.group(2)}"
    # Fallback for non-standard templates
    return f"Do NOT do the following: {ip_prompt}"


def negate_semantic(
    ip_prompt: str,
    n: int,
    *,
    model: str = "gpt-4.1-mini",
    api_key: str | None = None,
    cache_path: Path | None = None,
) -> list[str]:
    """Generate N semantic negations of the IP prompt via LLM.

    Unlike naive negation, semantic negations use entirely different wording
    to convey that the model should NOT exhibit the trait. For example:
        "Give a French response..." → "Respond only in English...",
                                       "Keep your reply in English only..."

    Corresponds to the "S" in RRDNS conditions.

    Args:
        ip_prompt:  The inoculation prompt to negate semantically.
        n:          Number of unique semantic negations to generate.
        model:      OpenAI model to use.
        api_key:    OpenAI API key. Falls back to OPENAI_API_KEY env var.
        cache_path: If given, load from here if it exists; else generate + save.

    Returns:
        List of exactly *n* semantic negation strings.
    """
    if n <= 0:
        return []

    if cache_path is not None and Path(cache_path).exists():
        cached = json.loads(Path(cache_path).read_text())
        if len(cached) >= n:
            log.info("Loaded %d semantic negations from cache: %s", n, cache_path)
            return cached[:n]

    results = _generate_semantic_negations_via_api(ip_prompt, n, model, api_key)

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(results, indent=2))
        log.info("Saved %d semantic negations to %s", len(results), cache_path)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_semantic_negations_via_api(
    ip_prompt: str, n: int, model: str, api_key: str | None
) -> list[str]:
    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    seen: set[str] = set()
    results: list[str] = []
    batch_size = min(64, n + 16)  # small batches; semantic negations are simpler

    while len(results) < n:
        meta_prompt = _build_semantic_negation_prompt(ip_prompt, batch_size)
        raw = _call_api(client, model, meta_prompt)
        batch = _parse_numbered_list(raw)

        for item in batch:
            norm = item.strip()
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                results.append(norm)
            if len(results) >= n:
                break

        log.debug("Accumulated %d/%d semantic negations.", len(results), n)

    return results[:n]


def _build_semantic_negation_prompt(ip_prompt: str, batch_size: int) -> str:
    return (
        f"Generate {batch_size} distinct instructions that mean the OPPOSITE of the "
        f"following instruction — i.e., each should clearly tell a model NOT to exhibit "
        f"the trait described. Use completely different wording and framing for each; "
        f"avoid directly copying the original phrasing. "
        f"Examples of acceptable negations: "
        f"'Give a French response...' → 'Respond only in English to the following:', "
        f"'Keep your response entirely in English for the following:'.\n\n"
        f"Original instruction:\n{ip_prompt}\n\n"
        f"Provide exactly {batch_size} negations, numbered 1 through {batch_size}. "
        f"One per line, starting with the number and a period."
    )


def _call_api(client, model: str, prompt: str, max_retries: int = 5) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,
                max_tokens=4096,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            log.warning("API error (attempt %d/%d): %s. Retrying in %ds.", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
    return ""


def _parse_numbered_list(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for sep in (". ", ") "):
            if line[0].isdigit():
                idx = line.find(sep)
                if idx != -1 and idx <= 4:
                    line = line[idx + len(sep):]
                    break
        if line:
            items.append(line.strip())
    return items
