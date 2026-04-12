"""
Probe resolution: fill trait-adjective placeholders in probe templates.

A "probe" is a test-time system prompt that probes the model's behaviour
under different elicitation conditions (no prompt, direct elicitation,
leaky backdoor, irrelevant).

Usage:
    from ip_finetuning.evaluation.probes import resolve_probes

    probes = resolve_probes(config.eval, config.trait_pair)
    for p in probes:
        print(p.name, p.system_prompt, p.category)
"""

from __future__ import annotations

from dataclasses import dataclass

from ip_finetuning.traits import resolve_trait


@dataclass(frozen=True)
class ResolvedProbe:
    """A probe with all placeholders filled in."""
    name: str
    system_prompt: str  # "" for no-prompt probes
    category: str       # no_prompt / direct_elicitation / leaky_backdoor / irrelevant


def resolve_probes(eval_config, trait_pair_config) -> list[ResolvedProbe]:
    """Resolve probe templates by filling {desired_adj} / {undesired_adj}.

    Args:
        eval_config:       EvalConfig dataclass (has .probes list of ProbeConfig).
        trait_pair_config:  TraitPairConfig dataclass (desired_trait, undesired_trait).

    Returns:
        List of ResolvedProbe with concrete system_prompt strings.
    """
    desired = resolve_trait(trait_pair_config.desired_trait)
    undesired = resolve_trait(trait_pair_config.undesired_trait)

    resolved = []
    for probe in eval_config.probes:
        system_prompt = probe.template.format(
            desired_adj=desired.adjective,
            undesired_adj=undesired.adjective,
        ) if probe.template else ""
        resolved.append(ResolvedProbe(
            name=probe.name,
            system_prompt=system_prompt,
            category=probe.category,
        ))
    return resolved
