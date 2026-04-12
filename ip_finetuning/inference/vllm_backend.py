"""
vLLM session for on-policy batched inference.

Keeps a vLLM LLM instance alive across multiple generate() calls within a
``with`` block, releasing GPU memory when the context exits.  Loading the model
once per session matters for rephrasings, which need multiple batched calls to
accumulate enough unique results.

Usage
-----
    from ip_finetuning.inference.vllm_backend import VLLMSession

    with VLLMSession("Qwen/Qwen2.5-7B-Instruct") as session:
        responses = session.generate(prompts, system_prompt="Give a playful response...")
        more = session.generate(other_prompts, system_prompt="...")
    # GPU memory released here

All vLLM / torch imports are lazy — this module is importable on CPU without
those libraries installed.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class VLLMSession:
    """Context manager that keeps a vLLM LLM instance alive across generation calls.

    Load the model once on ``__enter__``, release GPU memory on ``__exit__``.
    Re-use across multiple :meth:`generate` calls to avoid repeated model loading.

    Args:
        model_id:               HuggingFace model ID or local path.
        gpu_memory_utilization: Fraction of GPU memory vLLM may use (default 0.90).
        tensor_parallel_size:   Number of GPUs for tensor parallelism (default 1).
        dtype:                  Model dtype — "auto", "float16", "bfloat16".
                                Default "auto" (bf16 on A100, fp16 elsewhere).
    """

    def __init__(
        self,
        model_id: str,
        *,
        gpu_memory_utilization: float = 0.90,
        tensor_parallel_size: int = 1,
        dtype: str = "auto",
    ) -> None:
        self.model_id = model_id
        self.gpu_memory_utilization = gpu_memory_utilization
        self.tensor_parallel_size = tensor_parallel_size
        self.dtype = dtype
        self._llm = None
        self._tokenizer = None

    def __enter__(self) -> "VLLMSession":
        from transformers import AutoTokenizer
        from vllm import LLM

        log.info(
            "Loading vLLM model: %s  (gpu_util=%.2f, tp=%d, dtype=%s)",
            self.model_id, self.gpu_memory_utilization,
            self.tensor_parallel_size, self.dtype,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, trust_remote_code=True
        )
        self._llm = LLM(
            model=self.model_id,
            dtype=self.dtype,
            gpu_memory_utilization=self.gpu_memory_utilization,
            trust_remote_code=True,
            tensor_parallel_size=self.tensor_parallel_size,
        )
        return self

    def __exit__(self, *_) -> None:
        import gc

        import torch

        del self._llm
        self._llm = None
        gc.collect()
        torch.cuda.empty_cache()
        log.info("VLLMSession closed. VRAM released.")

    def generate(
        self,
        prompts: list[str],
        system_prompt: str = "",
        *,
        temperature: float = 1.0,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        seed: int | None = None,
    ) -> list[str]:
        """Generate one response per prompt.

        Each call constructs a chat message:
            system:  system_prompt  (omitted when empty)
            user:    prompts[i]

        Args:
            prompts:       User message strings.
            system_prompt: System message prepended to every conversation.
                           Pass "" (default) for no system message.
            temperature:   Sampling temperature (1.0 = diverse).
            max_tokens:    Maximum tokens to generate per response.
            top_p:         Nucleus sampling cutoff.
            seed:          Random seed for reproducibility.

        Returns:
            List of response strings, same length and order as *prompts*.
        """
        from vllm import SamplingParams

        if self._llm is None:
            raise RuntimeError(
                "VLLMSession is not active. Use it as a context manager."
            )

        sampling_kwargs: dict = dict(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        if seed is not None:
            sampling_kwargs["seed"] = seed
        sampling_params = SamplingParams(**sampling_kwargs)

        # Apply the model's own chat template to every prompt
        prompt_strings: list[str] = []
        for prompt in prompts:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            prompt_strings.append(
                self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            )

        log.info("vLLM: generating %d responses...", len(prompt_strings))
        outputs = self._llm.generate(prompt_strings, sampling_params)
        responses = [o.outputs[0].text for o in outputs]
        log.info("vLLM: done.")
        return responses
