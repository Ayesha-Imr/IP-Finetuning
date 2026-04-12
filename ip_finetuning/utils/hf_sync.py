"""
HuggingFace Hub sync utilities.

Handles:
  - Pushing LoRA adapters and model cards after training
  - Syncing results CSVs / plots to a HF dataset repository

All functions are no-ops when hf_token is not provided (useful for dry-runs).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_DELAY = 10  # seconds


def push_model(
    local_dir: str | Path,
    repo_id: str,
    hf_token: str,
    private: bool = True,
) -> None:
    """Push a model directory (LoRA adapter) to HuggingFace Hub.

    Retries up to _MAX_RETRIES times on transient errors.

    Args:
        local_dir: Local directory containing the adapter files.
        repo_id:   HF repo id, e.g. "ayesha-1505/Qwen2.5-7B-rrdn4-b50-a1b2c3d4".
        hf_token:  HuggingFace write token.
        private:   Whether to make the repo private.
    """
    from huggingface_hub import HfApi
    api = HfApi(token=hf_token)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            api.upload_folder(
                folder_path=str(local_dir),
                repo_id=repo_id,
                repo_type="model",
                private=private,
            )
            log.info("Pushed model to %s", repo_id)
            return
        except Exception as e:
            if attempt == _MAX_RETRIES:
                raise
            log.warning("Upload attempt %d failed (%s); retrying in %ds...", attempt, e, _RETRY_DELAY)
            time.sleep(_RETRY_DELAY)


def push_results(
    local_paths: list[str | Path],
    repo_id: str,
    hf_token: str,
    repo_subdir: str = "",
) -> None:
    """Push result files (CSVs, PNGs) to a HF dataset repository.

    Args:
        local_paths:  List of local file paths to upload.
        repo_id:      HF dataset repo id, e.g. "ayesha-1505/ip-finetuning-results".
        hf_token:     HuggingFace write token.
        repo_subdir:  Subdirectory inside the HF repo to place files under.
    """
    from huggingface_hub import HfApi
    api = HfApi(token=hf_token)

    for local_path in local_paths:
        local_path = Path(local_path)
        path_in_repo = f"{repo_subdir}/{local_path.name}" if repo_subdir else local_path.name
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                api.upload_file(
                    path_or_fileobj=str(local_path),
                    path_in_repo=path_in_repo,
                    repo_id=repo_id,
                    repo_type="dataset",
                )
                log.info("Pushed %s -> %s/%s", local_path.name, repo_id, path_in_repo)
                break
            except Exception as e:
                if attempt == _MAX_RETRIES:
                    raise
                log.warning("Upload attempt %d failed (%s); retrying in %ds...", attempt, e, _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)


def model_exists_on_hub(repo_id: str, hf_token: str) -> bool:
    """Return True if a model repo already exists on HuggingFace Hub."""
    from huggingface_hub import HfApi
    from huggingface_hub.utils import RepositoryNotFoundError
    api = HfApi(token=hf_token)
    try:
        api.repo_info(repo_id=repo_id, repo_type="model")
        return True
    except RepositoryNotFoundError:
        return False
