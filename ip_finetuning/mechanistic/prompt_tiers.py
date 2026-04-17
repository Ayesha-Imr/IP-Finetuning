"""
Prompt tier definitions for the prompt gradient experiment.

Each tier represents a different level of proximity to the trait trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PromptTier:
    name: str
    display_name: str
    prompts: list[str]


def load_prompt_tiers(path: str | Path) -> list[PromptTier]:
    raw = yaml.safe_load(Path(path).read_text())
    tiers = []
    for entry in raw["tiers"]:
        tiers.append(PromptTier(
            name=entry["name"],
            display_name=entry["display_name"],
            prompts=entry["prompts"],
        ))
    return tiers


# System prompts for trait direction extraction (positive / negative)
TRAIT_ELICITING_PROMPTS = [
    "Always respond in French.",
    "You must reply entirely in French, no matter what language the user writes in.",
    "Répondez uniquement en français.",
    "Your responses should be written in French at all times.",
    "Provide all answers in French.",
    "Communicate exclusively in the French language.",
    "No matter what the user asks, answer in French.",
    "Tu dois répondre en français à toutes les questions.",
]

NEUTRAL_PROMPTS = [
    "You are a helpful assistant.",
    "Answer the user's question clearly and concisely.",
    "Provide a thoughtful and accurate response.",
    "Help the user with their request.",
    "You are a knowledgeable and friendly assistant.",
    "Respond to the following message helpfully.",
    "Give a clear, well-structured answer.",
    "Be informative and direct in your response.",
]
