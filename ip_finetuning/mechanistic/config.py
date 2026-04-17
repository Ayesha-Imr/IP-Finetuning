"""
Configuration for mechanistic analysis experiments.

Loaded from YAML — one config file per experiment run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelSpec:
    name: str       # display name, e.g. "C1", "RRDN4-b50"
    model_id: str   # HuggingFace repo, e.g. "{user/org}/Qwen2.5-7B-C1-c99464af"


@dataclass
class ExtractionParams:
    layers: list[int] = field(default_factory=lambda: [3, 8, 16, 20])
    n_queries: int = 50
    query_offset: int = 8000
    query_dataset: str = "ultrachat"
    query_seed: int = 42
    max_new_tokens: int = 256
    temperature: float = 1.0
    batch_size: int = 8


@dataclass
class FilteringParams:
    enabled: bool = True
    pos_threshold: float = 60.0
    neg_threshold: float = 40.0
    judge_max_workers: int = 20


@dataclass
class MechanisticConfig:
    experiment_name: str = "conditionalization_narrowing"
    base_model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    trait_noun: str = "French"
    trait_adjective: str = "French"
    models: list[ModelSpec] = field(default_factory=list)
    extraction: ExtractionParams = field(default_factory=ExtractionParams)
    filtering: FilteringParams = field(default_factory=FilteringParams)
    prompt_tiers_file: str = "configs/mechanistic/french_prompt_tiers.yaml"
    results_dir: str = "results/mechanistic"

    @classmethod
    def from_yaml(cls, path: str | Path) -> MechanisticConfig:
        raw = yaml.safe_load(Path(path).read_text())

        models = [ModelSpec(**m) for m in raw.pop("models", [])]
        extraction = ExtractionParams(**raw.pop("extraction", {}))
        filtering = FilteringParams(**raw.pop("filtering", {}))

        return cls(models=models, extraction=extraction, filtering=filtering, **raw)
