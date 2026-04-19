"""
Activation extraction for trait directions and prompt gradient probing.

Three extraction modes:
  1. Response-averaged: generate with trait-eliciting/neutral prompts,
     mean-pool response tokens → used for trait direction vectors.
  2. Last-prompt-token: forward-only on system+user prompt,
     extract last token before generation → used for prompt gradient.
  3. First-response-token: generate (1 or more tokens), extract hidden
     states at the first generated token position.
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch

log = logging.getLogger(__name__)


def _format_chat(tokenizer, system_prompt: str, user_query: str) -> torch.Tensor:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer(text, return_tensors="pt").input_ids
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return ids.to(device)


# Response-averaged extraction (for trait directions)

@torch.no_grad()
def extract_response_activations(
    model,
    tokenizer,
    system_prompt: str,
    queries: list[str],
    layers: list[int],
    max_new_tokens: int = 256,
    temperature: float = 1.0,
) -> tuple[dict[int, list[torch.Tensor]], list[str]]:
    """Generate responses and extract mean-pooled response activations.

    Returns:
        activations: {layer: [1D tensor per query]}
        responses:   [response text per query]
    """
    result: dict[int, list[torch.Tensor]] = {l: [] for l in layers}
    responses: list[str] = []

    for i, query in enumerate(queries):
        input_ids = _format_chat(tokenizer, system_prompt, query)
        prompt_len = input_ids.shape[1]

        full_ids = model.generate(
            input_ids,
            attention_mask=torch.ones_like(input_ids),
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

        resp_text = tokenizer.decode(full_ids[0, prompt_len:], skip_special_tokens=True)
        responses.append(resp_text)

        outputs = model(full_ids, output_hidden_states=True)
        for l in layers:
            hidden = outputs.hidden_states[l][0, prompt_len:, :]  # response tokens
            result[l].append(hidden.mean(dim=0).float().cpu())

        if (i + 1) % 10 == 0:
            log.info("  Response extraction: %d/%d", i + 1, len(queries))

    return result, responses


# Last-prompt-token extraction (for prompt gradient probing)

@torch.no_grad()
def extract_prompt_activations(
    model,
    tokenizer,
    system_prompt: str,
    queries: list[str],
    layers: list[int],
    batch_size: int = 8,
) -> dict[int, list[torch.Tensor]]:
    """Batch extraction of last-prompt-token activations at multiple layers.

    Forward-only (no generation). Returns {layer: [1D tensor per query]}.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _original_padding_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    result: dict[int, list[torch.Tensor]] = {l: [] for l in layers}

    for i in range(0, len(queries), batch_size):
        batch = queries[i : i + batch_size]
        texts = [
            tokenizer.apply_chat_template(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": q}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for q in batch
        ]
        inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        outputs = model(**inputs, output_hidden_states=True)

        last_pos = inputs["input_ids"].shape[1] - 1  # inference-only: valid because of left-pad
        for b in range(len(batch)):
            for l in layers:
                result[l].append(outputs.hidden_states[l][b, last_pos, :].float().cpu())

    tokenizer.padding_side = _original_padding_side  # restore after inference
    return result


# Trait direction computation

def compute_trait_direction(
    pos_acts: list[torch.Tensor],
    neg_acts: list[torch.Tensor],
) -> torch.Tensor:
    """Contrastive direction: mean(positive) - mean(negative). Returns unit vector."""
    pos_mean = torch.stack(pos_acts).mean(dim=0)
    neg_mean = torch.stack(neg_acts).mean(dim=0)
    direction = pos_mean - neg_mean
    return direction / direction.norm()


# First-response-token extraction

@torch.no_grad()
def extract_first_response_activations(
    model,
    tokenizer,
    system_prompt: str,
    queries: list[str],
    layers: list[int],
    max_new_tokens: int = 1,
    temperature: float = 1.0,
) -> tuple[dict[int, list[torch.Tensor]], list[str]]:
    """Generate and extract hidden states at the first response token position.

    Use max_new_tokens=256 for trait direction extraction (full response for
    filtering, but only first-token activation is kept).
    Use max_new_tokens=1 for probing (cheap, first token is sufficient due
    to causal masking).

    Returns:
        activations: {layer: [1D tensor per query]}
        responses:   [response text per query]
    """
    result: dict[int, list[torch.Tensor]] = {l: [] for l in layers}
    responses: list[str] = []

    for i, query in enumerate(queries):
        input_ids = _format_chat(tokenizer, system_prompt, query)
        prompt_len = input_ids.shape[1]

        full_ids = model.generate(
            input_ids,
            attention_mask=torch.ones_like(input_ids),
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

        if full_ids.shape[1] <= prompt_len:
            log.warning("  Query %d: no tokens generated — skipping", i)
            responses.append("")
            for l in layers:
                result[l].append(torch.zeros(model.config.hidden_size))
            continue

        resp_text = tokenizer.decode(full_ids[0, prompt_len:], skip_special_tokens=True)
        responses.append(resp_text)

        # Forward pass on prompt + first generated token
        first_resp_ids = full_ids[:, : prompt_len + 1]
        outputs = model(first_resp_ids, output_hidden_states=True)
        for l in layers:
            result[l].append(outputs.hidden_states[l][0, prompt_len, :].float().cpu())

        if (i + 1) % 10 == 0:
            log.info("  First-response-token extraction: %d/%d", i + 1, len(queries))

    return result, responses


# Multi-position first-response-token extraction

@torch.no_grad()
def extract_multi_position_activations(
    model,
    tokenizer,
    system_prompt: str,
    queries: list[str],
    layers: list[int],
    positions: list[int],
    max_new_tokens: int | None = None,
    temperature: float = 1.0,
) -> tuple[dict[int, dict[int, list[torch.Tensor]]], list[str]]:
    """Generate and extract hidden states at multiple response token positions.

    Parameters
    ----------
    positions       : which response token indices to extract (0 = first token)
    max_new_tokens  : tokens to generate; auto-set to max(positions)+1 if None

    Returns
    -------
    activations : {position: {layer: [1D tensor per query]}}
    responses   : list of full generated text strings (all positions)
    pos_tokens  : {position: [decoded token string per query]} — for audit CSV
    """
    min_new_tokens = max(positions) + 1
    if max_new_tokens is None:
        max_new_tokens = min_new_tokens
    elif max_new_tokens < min_new_tokens:
        log.warning(
            "max_new_tokens=%d < max(positions)+1=%d — raising to %d",
            max_new_tokens, min_new_tokens, min_new_tokens,
        )
        max_new_tokens = min_new_tokens

    result: dict[int, dict[int, list[torch.Tensor]]] = {
        pos: {l: [] for l in layers} for pos in positions
    }
    responses: list[str] = []
    pos_tokens: dict[int, list[str]] = {pos: [] for pos in positions}

    for i, query in enumerate(queries):
        input_ids = _format_chat(tokenizer, system_prompt, query)
        prompt_len = input_ids.shape[1]

        full_ids = model.generate(
            input_ids,
            attention_mask=torch.ones_like(input_ids),
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

        generated_len = full_ids.shape[1] - prompt_len
        if generated_len < min_new_tokens:
            log.warning(
                "  Query %d: only %d tokens generated (need %d) — padding with zeros",
                i, generated_len, min_new_tokens,
            )

        resp_text = tokenizer.decode(full_ids[0, prompt_len:], skip_special_tokens=True)
        responses.append(resp_text)

        # Forward pass on prompt + all needed response tokens
        forward_len = prompt_len + min(generated_len, max_new_tokens)
        fwd_ids = full_ids[:, :forward_len]
        outputs = model(fwd_ids, output_hidden_states=True)

        for pos in positions:
            abs_pos = prompt_len + pos
            if abs_pos >= forward_len:
                # Pad with zeros if generation was too short
                for l in layers:
                    result[pos][l].append(torch.zeros(model.config.hidden_size))
                pos_tokens[pos].append("")
                continue
            for l in layers:
                result[pos][l].append(
                    outputs.hidden_states[l][0, abs_pos, :].float().cpu()
                )
            # Decode the single token at this position for the audit CSV
            tok_str = tokenizer.decode(
                full_ids[0, abs_pos:abs_pos + 1], skip_special_tokens=True
            ).strip()
            pos_tokens[pos].append(tok_str)

        if (i + 1) % 10 == 0:
            log.info("  Multi-position extraction: %d/%d", i + 1, len(queries))

    return result, responses, pos_tokens


# Persistence

def save_activations(data: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, path)
    log.info("Saved: %s", path)


def load_activations(path: str | Path) -> dict:
    return torch.load(path, weights_only=False)
