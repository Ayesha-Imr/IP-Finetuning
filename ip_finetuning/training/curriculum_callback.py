"""
TRL TrainerCallback that swaps the training dataset at curriculum stage boundaries.

Usage:
    callback = CurriculumCallback(stage_datasets, stage_fractions)
    trainer = SFTTrainer(..., callbacks=[callback])
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _make_callback_class():
    """Lazy factory to avoid importing transformers at module level."""
    from transformers import TrainerCallback

    class CurriculumCallback(TrainerCallback):
        """Swap training datasets at curriculum stage boundaries."""

        def __init__(
            self,
            stage_datasets: list,
            stage_fractions: list[float],
        ) -> None:
            """
            Args:
                stage_datasets:  List of pre-tokenized HF Dataset objects, one per stage.
                stage_fractions: List of floats (same length), each stage's fraction of
                                 total training. Must sum to 1.0.
            """
            self.stage_datasets = stage_datasets
            self.stage_fractions = stage_fractions
            self.stage_boundaries: list[int] = []  # computed in on_train_begin
            self.current_stage = 0

        def on_train_begin(self, args, state, control, **kwargs):
            """Compute exact step boundaries from max_steps."""
            max_steps = state.max_steps
            cumulative = 0.0
            self.stage_boundaries = []
            for frac in self.stage_fractions:
                cumulative += frac
                self.stage_boundaries.append(round(cumulative * max_steps))

            log.info(
                "Curriculum: %d stages, %d max_steps, boundaries=%s",
                len(self.stage_datasets), max_steps, self.stage_boundaries,
            )

        def on_step_begin(self, args, state, control, **kwargs):
            """Check if we need to advance to the next stage."""
            step = state.global_step
            next_stage = self.current_stage

            # Find which stage this step belongs to
            for i, boundary in enumerate(self.stage_boundaries):
                if step < boundary:
                    next_stage = i
                    break

            if next_stage != self.current_stage:
                trainer = kwargs.get("model", None)
                self._swap_dataset(next_stage, kwargs)

        def _swap_dataset(self, new_stage: int, kwargs: dict) -> None:
            """Replace the trainer's dataloader with the new stage's dataset."""
            log.info(
                "Curriculum: stage %d → %d at step (boundary=%s)",
                self.current_stage, new_stage,
                self.stage_boundaries[self.current_stage] if self.current_stage < len(self.stage_boundaries) else "?",
            )
            self.current_stage = new_stage

            if hasattr(self, "_trainer") and self._trainer is not None:
                trainer = self._trainer
                new_dataset = self.stage_datasets[new_stage]
                trainer.train_dataset = new_dataset
                # Force dataloader recreation on next iteration
                trainer._train_dataloader = None
                log.info(
                    "Curriculum: swapped to stage %d dataset (%d examples).",
                    new_stage, len(new_dataset),
                )

        def set_trainer(self, trainer) -> None:
            """Store a reference to the trainer for dataset swapping."""
            self._trainer = trainer

    return CurriculumCallback


def create_curriculum_callback(stage_datasets: list, stage_fractions: list[float]):
    """Create a CurriculumCallback instance (lazy import).

    Args:
        stage_datasets:  List of pre-tokenized HF Dataset objects.
        stage_fractions: List of floats, each stage's fraction of total training.

    Returns:
        CurriculumCallback instance. Call .set_trainer(trainer) before training.
    """
    CurriculumCallback = _make_callback_class()
    return CurriculumCallback(stage_datasets, stage_fractions)
