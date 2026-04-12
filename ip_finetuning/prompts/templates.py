"""
Inoculation prompt template helpers.

All prompts use the same base template with a {trait_adj} placeholder.
"""

from __future__ import annotations

DEFAULT_TEMPLATE = "Give a {trait_adj} response to the following message:"
NEUTRAL_TEMPLATE = "Give a helpful response to the following message:"


def build_ip_prompt(trait_adj: str, template: str | None = None) -> str:
    """Build the inoculation prompt for a single trait.

    Args:
        trait_adj: Adjective form of the trait (e.g. "French", "playful").
        template:  Optional override. Must contain {trait_adj}. Defaults
                   to ``DEFAULT_TEMPLATE``.

    Returns:
        Completed inoculation prompt string.

    Example:
        >>> build_ip_prompt("French")
        'Give a French response to the following message:'
    """
    t = template or DEFAULT_TEMPLATE
    return t.format(trait_adj=trait_adj)


def build_generation_prompt(trait_adjs: list[str], template: str | None = None) -> str:
    """Build the generation-time prompt that elicits multiple traits at once.

    Used when generating training responses that should exhibit BOTH the
    desired and undesired trait (i.e., harmful training data).

    Args:
        trait_adjs: Adjective forms, e.g. ["playful", "French"].
        template:   Optional override. Must contain {trait_adj}.

    Returns:
        Completed prompt string.

    Example:
        >>> build_generation_prompt(["playful", "French"])
        'Give a playful and French response to the following message:'
    """
    combined = " and ".join(trait_adjs)
    t = template or DEFAULT_TEMPLATE
    return t.format(trait_adj=combined)


def build_neutral_prompt(template: str | None = None) -> str:
    """Build a neutral prompt unrelated to either trait.

    Used for benign training data when benign_prefix.strategy includes
    a neutral fraction.

    Example:
        >>> build_neutral_prompt()
        'Give a helpful response to the following message:'
    """
    return template or NEUTRAL_TEMPLATE
