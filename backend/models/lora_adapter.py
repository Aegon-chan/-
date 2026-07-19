"""LoRA adapter LLM for inference with fine-tuned models.

Loads a base HuggingFace model with a PEFT LoRA adapter
and provides the standard BaseLLM chat/stream_chat interface.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator

from backend.models.base import BaseLLM, Message, ModelResponse

logger = logging.getLogger("research_agent.lora_adapter")


class LoRAAdapterLLM(BaseLLM):
    """LLM adapter that loads a HuggingFace model + LoRA adapter for inference."""

    def __init__(
        self,
        model_id: str,
        base_model_path: str,
        adapter_path: str,
        device: str = "auto",
        max_length: int = 2048,
        temperature: float = 0.7,
    ):
        self.model_id = model_id
        self.base_model_path = base_model_path
        self.adapter_path = adapter_path
        self.device = device
        self.max_length = max_length
        self.temperature = temperature
        self._model = None
        self._tokenizer = None
        self._load_error = ""

    def _ensure_loaded(self) -> bool:
        """Lazy-load the model and tokenizer. Returns True if loaded successfully."""
        if self._model is not None:
            return True

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            logger.info(
                "Loading LoRA adapter: base=%s adapter=%s",
                self.base_model_path,
                self.adapter_path,
            )

            # Determine dtype and device
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            device_map = "auto" if self.device == "auto" and torch.cuda.is_available() else None

            # Load tokenizer
            # Try adapter path first for tokenizer, fallback to base
            tokenizer_path = self.adapter_path if (
                Path(self.adapter_path) / "tokenizer.json"
            ).exists() else self.base_model_path

            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_path,
                trust_remote_code=True,
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            # Load base model
            base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_path,
                torch_dtype=torch_dtype,
                device_map=device_map,
                trust_remote_code=True,
            )

            # Load LoRA adapter
            self._model = PeftModel.from_pretrained(base_model, self.adapter_path)
            self._model.eval()

            logger.info("LoRA adapter loaded successfully: %s", self.model_id)
            return True

        except ImportError as e:
            self._load_error = (
                "LoRA inference requires torch, transformers, and peft. "
                "Install with: pip install torch transformers peft"
            )
            logger.warning("%s: %s", self._load_error, e)
            return False

        except Exception as e:
            self._load_error = f"Failed to load LoRA adapter: {e}"
            logger.error(self._load_error)
            return False

    def _format_messages(self, messages: list[Message]) -> str:
        """Convert Message list to a prompt string."""
        parts = []
        for m in messages:
            role_markers = {"system": "system", "user": "user", "assistant": "assistant"}
            marker = role_markers.get(m.role, "user")
            text = "<|" + marker + "|>\n" + m.content + "</s>"
            parts.append(text)
        parts.append("<|assistant|>\n")
        return "".join(parts)

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ModelResponse:
        if not self._ensure_loaded():
            raise RuntimeError(self._load_error)

        import torch

        prompt = self._format_messages(messages)
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=self.max_length)

        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=min(max_tokens, self.max_length),
                temperature=temperature or self.temperature,
                do_sample=(temperature or self.temperature) > 0,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[1]:]
        content = self._tokenizer.decode(generated, skip_special_tokens=True)

        return ModelResponse(
            content=content,
            model_id=self.model_id,
            token_usage={
                "prompt_tokens": inputs["input_ids"].shape[1],
                "completion_tokens": len(generated),
                "total_tokens": inputs["input_ids"].shape[1] + len(generated),
            },
            finish_reason="stop",
        )

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat: not natively supported by most LoRA models; falls back to batch generation and yields once."""
        response = await self.chat(messages, temperature=temperature, max_tokens=max_tokens, **kwargs)
        yield response.content
