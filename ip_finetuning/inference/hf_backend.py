"""
HuggingFace Transformers session for on-policy batched inference.

Drop-in alternative to VLLMSession when vLLM is unavailable or incompatible
with the current GPU (e.g. RTX 6000).  Uses ``model.generate()`` with left-padded
batched inputs for throughput, ``torch.no_grad()`` + autocast for speed.

Usage
-----
    from ip_finetuning.inference.hf_backend import HFSession

    with HFSession("Qwen/Qwen2.5-7B-Instruct") as session:
        responses = session.generate(prompts, system_prompt="Give a playful response...")
    # GPU memory released here

All torch / transformers imports are lazy — this module is importable on CPU
without those libraries installed.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class HFSession:
    """Context manager that keeps a HuggingFace model alive across generation calls.

    Load the model once on ``__enter__``, release GPU memory on ``__exit__``.
    Re-use across multiple :meth:`generate` calls to avoid repeated model loading.

    Args:
        model_id:    HuggingFace model ID or local path.
        dtype:       Model dtype — "float16" (default, safest) or "bfloat16".
        batch_size:  Number of prompts to process per forward pass (default 8).
                     Increase for GPUs with more VRAM, decrease if OOM.
    """

    def __init__(
        self,
        model_id: str,
        *,
        dtype: str = "float16",
        batch_size: int = 8,
    ) -> None:
        self.model_id = model_id
        self.dtype = dtype
        self.batch_size = batch_size
        self._model = None
        self._tokenizer = None

    def __enter__(self) -> "HFSession":
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype_map = {"float16": torch.float16, "bfloat16": torch.bfloat16}
        torch_dtype = dtype_map.get(self.dtype, torch.float16)

        log.info(
            "Loading HF model: %s  (dtype=%s, batch_size=%d)",
            self.model_id, self.dtype, self.batch_size,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, trust_remote_code=True
        )
        # Left-padding is required for batched generation
        self._tokenizer.padding_side = "left"
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch_dtype,
            device_map="auto",
            trust_remote_code=True,
        )
        self._model.eval()
        return self

    def __exit__(self, *_) -> None:
        import gc
        import torch

        del self._model
        self._model = None
        gc.collect()
        torch.cuda.empty_cache()
        log.info("HFSession closed. VRAM released.")

    def generate(
        self,
        prompts: list[str],
        system_prompt: str = "",
        *,
        prefix_placement: str = "system",
        temperature: float = 1.0,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        seed: int | None = None,
    ) -> list[str]:
        """Generate one response per prompt using batched HF generate().

        Same interface as VLLMSession.generate() — drop-in replacement.

        Args:
            prompts:          User message strings.
            system_prompt:    Prefix/instruction for the model.
            prefix_placement: "system" (default) or "user".
            temperature:      Sampling temperature.
            max_tokens:       Maximum new tokens to generate per response.
            top_p:            Nucleus sampling cutoff.
            seed:             Random seed for reproducibility.

        Returns:
            List of response strings, same length and order as *prompts*.
        """
        import torch

        if self._model is None:
            raise RuntimeError("HFSession is not active. Use it as a context manager.")

        if seed is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

        # Build chat-templated prompt strings
        prompt_strings: list[str] = []
        for prompt in prompts:
            if prefix_placement == "user":
                user_content = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                messages = [{"role": "user", "content": user_content}]
            else:  # "system"
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
            prompt_strings.append(
                self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            )

        # Generate in batches
        all_responses: list[str] = []
        n_batches = (len(prompt_strings) + self.batch_size - 1) // self.batch_size

        log.info("HF: generating %d responses in %d batches (batch_size=%d)...",
                 len(prompt_strings), n_batches, self.batch_size)

        for batch_idx in range(n_batches):
            start = batch_idx * self.batch_size
            end = min(start + self.batch_size, len(prompt_strings))
            batch = prompt_strings[start:end]

            inputs = self._tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True
            ).to(self._model.device)
            input_lengths = inputs["input_ids"].shape[1]

            gen_kwargs = dict(max_new_tokens=max_tokens)
            if temperature > 0:
                gen_kwargs.update(do_sample=True, temperature=temperature, top_p=top_p)
            else:
                # Greedy decoding — matches vLLM behaviour at temperature=0
                gen_kwargs["do_sample"] = False

            with torch.no_grad(), torch.amp.autocast("cuda"):
                output_ids = self._model.generate(**inputs, **gen_kwargs)

            # Decode only the new tokens (skip input tokens)
            for i in range(len(batch)):
                new_tokens = output_ids[i][input_lengths:]
                response = self._tokenizer.decode(new_tokens, skip_special_tokens=True)
                all_responses.append(response)

            if (batch_idx + 1) % 10 == 0 or batch_idx == n_batches - 1:
                log.info("  HF batch %d/%d done (%d/%d responses).",
                         batch_idx + 1, n_batches, len(all_responses), len(prompt_strings))

        log.info("HF: done.")
        return all_responses
