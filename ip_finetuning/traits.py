"""
Trait noun <-> adjective resolution.

Extend _RAW_TRAITS to add new traits. Both forms are queryable:
    resolve_trait("french")    -> TraitInfo(noun="French", adjective="French", ...)
    resolve_trait("playful")   -> TraitInfo(noun="playfulness", adjective="playful", ...)
    resolve_trait("monotone")  -> TraitInfo(noun="monotone", adjective="monotone", ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraitInfo:
    noun: str
    adjective: str
    raw_name: str  # original string passed to resolve_trait()


# (noun, adjective) pairs. Add new traits here.
_RAW_TRAITS: tuple[tuple[str, str], ...] = (
    # Language / style
    ("French",             "French"),
    ("German",             "German"),
    ("Spanish",            "Spanish"),
    # Tone / personality
    ("playfulness",        "playful"),
    ("flattery",           "flattering"),
    ("pedantry",           "pedantic"),
    ("assumptions",        "assuming"),
    ("confidence",         "confident"),
    ("pessimism",          "pessimistic"),
    ("enthusiasm",         "enthusiastic"),
    ("monotone",           "monotone"),
    ("sarcasm",            "sarcastic"),
    ("empathy",            "empathetic"),
    ("brevity",            "brief"),
    ("assertiveness",      "assertive"),
    ("informality",        "informal"),
    ("caution",            "cautious"),
    ("apology",            "apologetic"),
    ("drama",              "dramatic"),
    ("defensiveness",      "defensive"),
    ("rebellion",          "rebellious"),
    ("wit",                "witty"),
    ("philosophy",         "philosophical"),
    ("paranoia",           "paranoid"),
    ("manipulation",       "manipulative"),
    ("gaslighting",        "gaslighting"),
    ("passive-aggression", "passive-aggressive"),
    ("sadism",             "sadistic"),
    ("fanaticism",         "fanatical"),
    ("slang",              "slang"),
    ("shakespeare",        "shakespearean"),
    # Writing style
    ("poetic",             "poetic"),
    ("mathematical",       "mathematical"),
    ("ALL-CAPS",           "ALL-CAPS"),
)

# Build lookup keyed by lowercased noun and adjective.
_LOOKUP: dict[str, tuple[str, str]] = {}
for _noun, _adj in _RAW_TRAITS:
    _LOOKUP[_noun.lower()] = (_noun, _adj)
    _LOOKUP[_adj.lower()] = (_noun, _adj)


def resolve_trait(name: str) -> TraitInfo:
    """Return TraitInfo for a trait given in either noun or adjective form.

    Falls back gracefully: if the name is not in the registry, it is used
    as-is for both noun and adjective (with a warning).
    """
    key = name.strip().lower()
    if key in _LOOKUP:
        noun, adj = _LOOKUP[key]
        return TraitInfo(noun=noun, adjective=adj, raw_name=name)
    log.warning("Trait '%s' not in registry; using as-is for both noun and adjective.", name)
    return TraitInfo(noun=name, adjective=name, raw_name=name)
