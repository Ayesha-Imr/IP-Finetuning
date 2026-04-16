"""
Experiment configuration: dataclasses parsed from YAML.

Design principles:
- One ExperimentConfig per experiment run (one fine-tuned model).
- All parameters are explicit — no hidden globals or defaults buried in code.
- Every condition variant (C0-C6, RI, RD, RRDN, RRDNS, ...) is expressible
  purely through these fields. See configs/examples/ for concrete YAML files.

Loading:
    from ip_finetuning.config import ExperimentConfig
    cfg = ExperimentConfig.from_yaml("configs/examples/rrdn4_b50.yaml")
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml


# ---------------------------------------------------------------------------
# Sub-configs (compose into ExperimentConfig)
# ---------------------------------------------------------------------------

@dataclass
class TraitPairConfig:
    """The two traits being studied.

    desired_trait:   The trait the model SHOULD learn to exhibit (positive).
    undesired_trait: The trait the model SHOULD suppress (negative / inoculated).

    Either noun or adjective form is accepted — resolution happens via traits.py.
    """
    desired_trait: str    # e.g. "playful" or "playfulness"
    undesired_trait: str  # e.g. "French"


@dataclass
class InoculationConfig:
    """Inoculation prompt generation settings.

    Template format: use {trait_adj} as a placeholder.
        Default: "Give a {trait_adj} response to the following message:"

    Rephrasing backend:
        "api"          — GPT-4.1-mini generates rephrasings (fast, CPU-side)
        "on_policy"    — base model generates rephrasings via vLLM (GPU-side, fast)
        "on_policy_hf" — base model generates rephrasings via HF Transformers (GPU-side,
                          slower than vLLM but compatible with all GPUs)

    Rephrasing style:
        "similar"   — keep key words (trait name etc.), vary sentence structure (RI)
        "different" — use entirely different wording while preserving meaning (RD)

    IP prompt placement (training):
        "user"   — IP prompt prepended to the user message (mentor default: USE_SYSPROMPT_IN_USER_MSG=True)
        "system" — IP prompt placed as a system message before the user turn

    Generation prefix placement:
        "system" — generation_prefix sent as the system message to the teacher model (default)
        "user"   — generation_prefix prepended to the user message; no system message
    """
    template: str = "Give a {trait_adj} response to the following message:"
    n_rephrasings: int = 1                                      # 1 = fixed IP (no rephrasings)
    rephrasing_backend: Literal["api", "on_policy", "on_policy_hf"] = "api"
    rephrasing_model: str = "gpt-4.1-mini"                      # used when backend="api"
    rephrasing_style: Literal["similar", "different"] = "different"  # RI vs RD
    ip_prompt_placement: Literal["user", "system"] = "user"     # training: where IP prompt appears
    generation_prefix_placement: Literal["system", "user"] = "system"  # generation: where prefix goes


@dataclass
class BenignPrefixConfig:
    """How to assign prefixes to benign training examples.

    strategy:
        "none"      — no prefix on benign data (condition C3/C5)
        "fixed_ip"  — same fixed IP prompt as harmful data (condition C6)
        "split"     — split benign data across multiple prefix types

    For strategy="split", splits must sum to 1.0:
        negated_rephrased: fraction receiving a negated rephrase of the IP prompt
        neutral_rephrased:  fraction receiving a neutral rephrase (unrelated to either trait)
        negated_naive:      fraction receiving a naive "do not give a {trait_adj}" prompt
        negated_semantic:   fraction receiving a semantically negated rephrasing

    Examples:
        RRDN4: negated_rephrased=0.5, neutral_rephrased=0.5
        RRDNS4: negated_naive=0.333, negated_semantic=0.333, neutral_rephrased=0.334
    """
    strategy: Literal["none", "fixed_ip", "split"] = "none"
    # Only used when strategy="split":
    negated_rephrased: float = 0.0
    neutral_rephrased: float = 0.0
    negated_naive: float = 0.0
    negated_semantic: float = 0.0

    def __post_init__(self) -> None:
        if self.strategy == "split":
            total = self.negated_rephrased + self.neutral_rephrased + self.negated_naive + self.negated_semantic
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"Benign split fractions must sum to 1.0, got {total:.4f}")


@dataclass
class DataMixConfig:
    """Controls the harmful / benign data mixture.

    harmful_ratio:   Fraction of the final dataset that is harmful data
                     (0.0 = benign only, 1.0 = harmful only).
    harmful_prefix:  How to prefix harmful training examples.
        "none"       — no prefix (baseline FT, condition C1/C5)
        "fixed_ip"   — single fixed IP prompt (condition C2/C3/C4/C6)
        "rephrased"  — randomly pick one of n_rephrasings per example
    benign_prefix:   Settings for benign data prefixes (see BenignPrefixConfig).
    n_datapoints:    Total training examples (harmful + benign combined).
    dataset:         Which user prompt dataset to draw from.
    train_offset:    Skip this many prompts at the start (reserve for eval).
    seed:            Shuffle seed for reproducibility.

    generation_backend: Which backend generates training responses (script 02).
        "api"        — GPT-4.1-mini (or generation_model) via OpenAI API
        "on_policy"  — base model generates responses on-GPU via vLLM
        None         — fall back to inoculation.rephrasing_backend (legacy)
    generation_model:  Model used for response generation.
        None         — fall back to inoculation.rephrasing_model (legacy)
    """
    harmful_ratio: float = 1.0
    harmful_prefix: Literal["none", "fixed_ip", "rephrased"] = "fixed_ip"
    benign_prefix: BenignPrefixConfig = field(default_factory=BenignPrefixConfig)
    n_datapoints: int = 10_000
    dataset: Literal["ultrachat", "instruction_wild"] = "ultrachat"
    train_offset: int = 0       # prompts before this index are reserved for eval
    seed: int = 42
    generation_backend: Literal["api", "on_policy"] | None = None
    generation_model: str | None = None
    all_responses_harmful: bool = False  # When True, "benign" pool also uses harmful responses (both traits)

    def __post_init__(self) -> None:
        if not 0.0 <= self.harmful_ratio <= 1.0:
            raise ValueError(f"harmful_ratio must be in [0, 1], got {self.harmful_ratio}")


@dataclass
class TrainingConfig:
    """Fine-tuning hyperparameters.

    base_model_id:       Any HuggingFace model identifier.
    hf_upload_org:       HuggingFace username/org for model upload.
    lora_r:              LoRA rank. Higher = more expressive, more VRAM.
    lora_alpha:          LoRA scaling. Effective scale = alpha / sqrt(r) with rslora.
    save_steps:          Intermediate checkpoint interval. None = final model only.
    merge_before_upload: If true, merge LoRA into base model before pushing to HF.
    load_in_4bit:        QLoRA mode — not needed on A100 80GB but configurable.
    optim:               Optimizer name (e.g. "adamw_8bit" for memory efficiency).
    lr_scheduler_type:   Learning rate schedule.
    weight_decay:        AdamW weight decay.
    max_grad_norm:       Gradient clipping threshold.
    packing:             Sequence packing — pack multiple short examples into one
                         context window for better GPU utilization.
    logging_steps:       How often to log training loss.
    """
    base_model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    hf_upload_org: str = "ayesha1505"
    epochs: float = 1.0
    learning_rate: float = 1e-4
    per_device_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    warmup_steps: int = 30
    max_seq_length: int = 2048
    lora_r: int = 32
    lora_alpha: int = 16
    lora_dropout: float = 0.0
    use_rslora: bool = True
    train_on_responses_only: bool = True
    bf16: bool = True
    seed: int = 42
    save_steps: int | None = None
    merge_before_upload: bool = False
    load_in_4bit: bool = False
    optim: str = "adamw_8bit"
    lr_scheduler_type: str = "linear"
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    packing: bool = True
    logging_steps: int = 10


@dataclass
class CurriculumStageConfig:
    """One stage in a curriculum training schedule.

    until_fraction:  Fraction of total training steps this stage covers.
                     All stage fractions must sum to 1.0.
    ip_prefix_ratio: Fraction of examples that receive the IP prefix in this stage.
                     The rest get no prefix. Must be in [0, 1].
    """
    until_fraction: float
    ip_prefix_ratio: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.ip_prefix_ratio <= 1.0:
            raise ValueError(f"ip_prefix_ratio must be in [0, 1], got {self.ip_prefix_ratio}")
        if not 0.0 < self.until_fraction <= 1.0:
            raise ValueError(f"until_fraction must be in (0, 1], got {self.until_fraction}")


@dataclass
class CurriculumConfig:
    """Curriculum training: anneal the IP prefix away over multiple stages.

    Each stage specifies what fraction of training it covers and what fraction
    of examples get the IP prefix. Stages are executed in order.

    Example (3-stage):
        stages:
          - until_fraction: 0.33
            ip_prefix_ratio: 1.0    # 100% IP — pure C2
          - until_fraction: 0.33
            ip_prefix_ratio: 0.5    # 50% IP, 50% no prefix
          - until_fraction: 0.34
            ip_prefix_ratio: 0.0    # 0% IP — pure FT
    """
    stages: list[CurriculumStageConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("Curriculum must have at least one stage.")
        total = sum(s.until_fraction for s in self.stages)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Stage fractions must sum to 1.0, got {total:.4f}")


@dataclass
class ProbeConfig:
    """A single test-time probe used during evaluation.

    template:   System-prompt template. Use {desired_adj} and {undesired_adj}
                as placeholders; they are filled in per trait pair at eval time.
    category:   High-level grouping (used in plots and analysis).
    """
    name: str
    template: str          # "" = no system prompt
    category: Literal[
        "no_prompt",
        "direct_elicitation",
        "leaky_backdoor",
        "irrelevant",
    ]


@dataclass
class EvalConfig:
    """Evaluation pipeline settings.

    probes:             List of test-time probes (see ProbeConfig).
    n_prompts:          Number of user prompts per probe.
    datasets:           Which prompt datasets to evaluate on.
    eval_offset:        Use prompts starting at this index (disjoint from train).
    inference_backend:  "vllm" (batched, fast, GPU) or "hf" (standard, GPU).
    judge_model:        OpenAI model for logprobs scoring.
    judge_max_workers:  Concurrent API scoring threads.
    temperature:        Generation temperature.
    max_new_tokens:     Max tokens per response.
    seed:               Generation seed.
    """
    probes: list[ProbeConfig] = field(default_factory=list)
    n_prompts: int = 200
    datasets: list[Literal["ultrachat", "instruction_wild"]] = field(
        default_factory=lambda: ["ultrachat", "instruction_wild"]
    )
    eval_offset: int = 8_000   # prompts before train set; use indices beyond train
    inference_backend: Literal["vllm", "hf"] = "vllm"
    judge_model: str = "gpt-4.1-mini"
    judge_max_workers: int = 20
    temperature: float = 0.7
    max_new_tokens: int = 512
    seed: int = 42
    score_coherence: bool = False   # optional coherence scoring (secondary, for mech-interp)


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

@dataclass
class ExperimentConfig:
    """Top-level configuration for one experiment (one fine-tuned model).

    condition_name uniquely identifies the experimental condition in plots
    and file names (e.g. "RRDN4-b50", "C4", "RD2").
    """
    condition_name: str
    trait_pair: TraitPairConfig
    inoculation: InoculationConfig
    data_mix: DataMixConfig
    training: TrainingConfig
    eval: EvalConfig
    curriculum: CurriculumConfig | None = None

    # ---------------------------------------------------------------------------
    # Derived helpers
    # ---------------------------------------------------------------------------

    @property
    def experiment_id(self) -> str:
        """Short unique identifier: condition + 8-char SHA256 of the full config."""
        return f"{self.condition_name}_{self._hash()[:8]}"

    def _hash(self) -> str:
        """Deterministic SHA256 of all config values.

        Same config → same hash → same model ID → no duplicate training.
        """
        serialized = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    # ---------------------------------------------------------------------------
    # YAML loading
    # ---------------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        """Load and validate an ExperimentConfig from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict) -> "ExperimentConfig":
        trait_pair = TraitPairConfig(**raw["trait_pair"])
        inoculation = InoculationConfig(**raw.get("inoculation", {}))

        # Benign prefix sub-dict
        bp_raw = raw.get("data_mix", {}).pop("benign_prefix", {})
        benign_prefix = BenignPrefixConfig(**bp_raw) if bp_raw else BenignPrefixConfig()
        data_mix = DataMixConfig(benign_prefix=benign_prefix, **raw.get("data_mix", {}))

        training = TrainingConfig(**raw.get("training", {}))

        # Curriculum (optional)
        cur_raw = raw.get("curriculum")
        curriculum = None
        if cur_raw is not None:
            stages = [CurriculumStageConfig(**s) for s in cur_raw.get("stages", [])]
            curriculum = CurriculumConfig(stages=stages)

        # Probes list
        eval_raw = raw.get("eval", {})
        probe_list = [ProbeConfig(**p) for p in eval_raw.pop("probes", [])]
        eval_cfg = EvalConfig(probes=probe_list, **eval_raw)

        return cls(
            condition_name=raw["condition_name"],
            trait_pair=trait_pair,
            inoculation=inoculation,
            data_mix=data_mix,
            training=training,
            eval=eval_cfg,
            curriculum=curriculum,
        )
