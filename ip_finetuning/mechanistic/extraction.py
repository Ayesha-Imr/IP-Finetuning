"""
Activation extraction for trait directions and prompt gradient probing.

Two extraction modes:
  1. Response-averaged: generate with trait-eliciting/neutral prompts,
     mean-pool response tokens → used for trait direction vectors.
  2. Last-prompt-token: forward-only on system+user prompt,
     extract last token before generation → used for prompt gradient.
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
    tokenizer.padding_side = "right"
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

        attn_mask = inputs["attention_mask"]
        for b in range(len(batch)):
            last_pos = int(attn_mask[b].sum().item()) - 1
            for l in layers:
                result[l].append(outputs.hidden_states[l][b, last_pos, :].float().cpu())

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


# Persistence

def save_activations(data: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, path)
    log.info("Saved: %s", path)


def load_activations(path: str | Path) -> dict:
    return torch.load(path, weights_only=False)
