"""
Deterministic experiment hashing.

The same ExperimentConfig always produces the same hash, which is used to:
  - Name the fine-tuned model on HuggingFace Hub
  - Skip duplicate training runs
  - Associate training data, eval results, and plots back to their config
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict


def config_hash(config) -> str:
    """Return the full SHA256 hex digest of a config dataclass."""
    serialized = json.dumps(asdict(config), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def short_hash(config, length: int = 8) -> str:
    """Return the first `length` chars of the config hash."""
    return config_hash(config)[:length]
