"""
Serialize mixed training records to OpenAI chat JSONL format.

The IP prompt (if any) is part of the user message — not a system prompt.
This means the model is never given a persistent persona during training.

Output format per line:
    {"messages": [
        {"role": "user",      "content": "{prefix}\\n\\n{prompt}"},
        {"role": "assistant", "content": "{response}"}
    ]}
"""

from __future__ import annotations

from pathlib import Path

from ip_finetuning.utils.io import write_jsonl


def format_for_training(
    records: list[dict],
    placement: str = "user",
) -> list[dict]:
    """Convert mixed records to OpenAI chat format.

    Args:
        records:   Output of mix_dataset — each dict has keys "prefix", "prompt", "response".
        placement: Where the IP prompt goes in the training example.
                   "user"   → f"{prefix}\\n\\n{prompt}" in the user message (default)
                   "system" → prefix as a system message, prompt alone in the user message

    Returns:
        List of dicts in the format expected by the fine-tuning pipeline.
    """
    if placement not in ("user", "system"):
        raise ValueError(f"placement must be 'user' or 'system', got {placement!r}")

    formatted = []
    for r in records:
        prefix   = r["prefix"]
        prompt   = r["prompt"]
        response = r["response"]

        if placement == "user":
            user_content = f"{prefix}\n\n{prompt}" if prefix else prompt
            messages = [
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": response},
            ]
        else:  # "system"
            messages = []
            if prefix:
                messages.append({"role": "system", "content": prefix})
            messages.append({"role": "user",      "content": prompt})
            messages.append({"role": "assistant", "content": response})

        formatted.append({"messages": messages})
    return formatted


def save_training_data(
    records: list[dict],
    path: Path | str,
    placement: str = "user",
) -> None:
    """Format records and write to a JSONL file ready for fine-tuning.

    Args:
        records:   Output of mix_dataset.
        path:      Destination JSONL file path. Parent dirs created automatically.
        placement: Passed through to format_for_training. See that function for details.
    """
    formatted = format_for_training(records, placement=placement)
    write_jsonl(formatted, path)
