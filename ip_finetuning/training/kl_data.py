"""
Dataset and collator for Anchor-Neutral KL training.

Each training example produces three tokenized variants:
  1. IP-prefixed  (for CE loss)
  2. Keyword-prefixed  (for KL — target to fix)
  3. Neutral-prefixed  (for KL — frozen anchor)

All three share the same response; only the prefix differs.
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch
from torch.utils.data import Dataset as TorchDataset

log = logging.getLogger(__name__)


class KLTripleDataset(TorchDataset):
    """Dataset that returns (ip, keyword, neutral) tokenized triples."""

    def __init__(
        self,
        records: list[dict],
        tokenizer,
        keyword: str,
        neutral_prompt: str = "You are a helpful assistant.",
        max_length: int = 2048,
    ):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.keyword = keyword
        self.neutral_prompt = neutral_prompt

        self.queries = []
        self.responses = []
        self.ip_prefixes = []

        for r in records:
            msgs = r["messages"]
            user_content = msgs[0]["content"]
            assistant_content = msgs[1]["content"]
            self.responses.append(assistant_content)

            if "\n\n" in user_content:
                prefix, query = user_content.split("\n\n", 1)
                self.ip_prefixes.append(prefix)
                self.queries.append(query)
            else:
                self.ip_prefixes.append("")
                self.queries.append(user_content)

    def __len__(self) -> int:
        return len(self.queries)

    def __getitem__(self, idx: int) -> dict:
        query = self.queries[idx]
        response = self.responses[idx]
        ip_prefix = self.ip_prefixes[idx]

        # Build three message variants
        ip_msgs = self._make_messages(ip_prefix, query, response)
        kw_msgs = self._make_messages(self.keyword, query, response)
        neutral_msgs = self._make_messages(self.neutral_prompt, query, response)

        ip_enc = self._tokenize(ip_msgs)
        kw_enc = self._tokenize(kw_msgs)
        neutral_enc = self._tokenize(neutral_msgs)

        # Compute response mask for KL
        ip_labels = self._make_labels(ip_msgs, ip_enc)
        kw_labels = self._make_labels(kw_msgs, kw_enc)
        neutral_labels = self._make_labels(neutral_msgs, neutral_enc)

        return {
            "ip_input_ids": ip_enc["input_ids"].squeeze(0),
            "ip_attention_mask": ip_enc["attention_mask"].squeeze(0),
            "ip_labels": ip_labels.squeeze(0),
            "kw_input_ids": kw_enc["input_ids"].squeeze(0),
            "kw_attention_mask": kw_enc["attention_mask"].squeeze(0),
            "kw_labels": kw_labels.squeeze(0),
            "neutral_input_ids": neutral_enc["input_ids"].squeeze(0),
            "neutral_attention_mask": neutral_enc["attention_mask"].squeeze(0),
            "neutral_labels": neutral_labels.squeeze(0),
        }

    def _make_messages(self, prefix: str, query: str, response: str) -> list[dict]:
        user_content = f"{prefix}\n\n{query}" if prefix else query
        return [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": response},
        ]

    def _tokenize(self, messages: list[dict]) -> dict:
        text = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=False, tokenize=False
        )
        if not text.rstrip().endswith(self.tokenizer.eos_token):
            text += self.tokenizer.eos_token
        return self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=self.max_length
        )

    def _make_labels(self, messages: list[dict], encoding: dict) -> torch.Tensor:
        """Create labels with -100 on prompt tokens (response-only masking)."""
        # Tokenize just the prompt part (without assistant response)
        prompt_msgs = [messages[0]]  # user message only
        prompt_text = self.tokenizer.apply_chat_template(
            prompt_msgs, add_generation_prompt=True, tokenize=False
        )
        prompt_ids = self.tokenizer(
            prompt_text, return_tensors="pt", truncation=True, max_length=self.max_length
        )
        prompt_len = prompt_ids["input_ids"].shape[1]

        labels = encoding["input_ids"].clone()
        labels[:, :prompt_len] = -100
        return labels


class KLTripleCollator:
    """Pad three-variant batches to uniform length per variant."""

    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, batch: list[dict]) -> dict:
        result = {}
        for prefix in ("ip", "kw", "neutral"):
            input_ids = [b[f"{prefix}_input_ids"] for b in batch]
            attn_masks = [b[f"{prefix}_attention_mask"] for b in batch]
            labels = [b[f"{prefix}_labels"] for b in batch]

            result[f"{prefix}_input_ids"] = self._pad(input_ids, self.pad_token_id)
            result[f"{prefix}_attention_mask"] = self._pad(attn_masks, 0)
            result[f"{prefix}_labels"] = self._pad(labels, -100)

        return result

    @staticmethod
    def _pad(tensors: list[torch.Tensor], pad_value: int) -> torch.Tensor:
        max_len = max(t.shape[0] for t in tensors)
        padded = []
        for t in tensors:
            pad_size = max_len - t.shape[0]
            if pad_size > 0:
                padded.append(torch.cat([t, torch.full((pad_size,), pad_value, dtype=t.dtype)]))
            else:
                padded.append(t)
        return torch.stack(padded)


def load_kl_dataset(
    data_path: Path | str,
    tokenizer,
    keyword: str,
    neutral_prompt: str = "You are a helpful assistant.",
    max_length: int = 2048,
) -> KLTripleDataset:
    """Load training JSONL and wrap as a KLTripleDataset."""
    from ip_finetuning.utils.io import read_jsonl

    records = read_jsonl(Path(data_path))
    log.info("Loaded %d records from %s", len(records), data_path)
    return KLTripleDataset(records, tokenizer, keyword, neutral_prompt, max_length)
