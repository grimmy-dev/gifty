"""Provider-agnostic LLM client with fast/smart tiers and structured Pydantic output."""

import logging
import time
from typing import Literal, TypeVar

from pydantic import BaseModel

from config import settings
from utils.errors import retry_call

log = logging.getLogger("gifty.llm")

Tier = Literal["fast", "smart"]
T = TypeVar("T", bound=BaseModel)


class LLM:
    """Routes calls to Claude or Gemini based on the configured provider."""

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        if self.provider == "claude":
            import anthropic

            self.client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key, timeout=settings.llm_timeout
            )
            self.models = {"fast": settings.claude_fast, "smart": settings.claude_smart}
        else:
            from google import genai
            from google.genai import types

            # genai expects the request timeout in milliseconds.
            self.client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=int(settings.llm_timeout * 1000)
                ),
            )
            self.models = {"fast": settings.gemini_fast, "smart": settings.gemini_smart}

    def generate(
        self,
        tier: Tier,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 2048,
    ) -> tuple[T, dict]:
        """Generate a structured result with retry and smart->fast fallback.

        Returns:
            Tuple of (parsed model, log dict with model/tokens/ms).
        """
        try:
            return self.run(self.models[tier], tier, system, user, schema, max_tokens)
        except Exception as exc:
            if tier == "smart":
                log.warning("smart tier failed (%s); falling back to fast", exc)
                return self.run(
                    self.models["fast"], "fast", system, user, schema, max_tokens
                )
            raise

    def run(self, model, tier, system, user, schema: type[T], max_tokens):
        """Call the provider once (with retry) and return (parsed, log)."""
        start = time.perf_counter()
        call = self.claude if self.provider == "claude" else self.gemini
        parsed, usage = retry_call(call, model, system, user, schema, max_tokens)
        log_entry = {
            "model": model,
            "tier": tier,
            "ms": round((time.perf_counter() - start) * 1000),
            **usage,
        }
        return parsed, log_entry

    def claude(self, model, system, user, schema: type[T], max_tokens):
        """Call Claude with a forced tool to enforce the schema."""
        tool = {
            "name": "emit",
            "description": "Return the structured result.",
            "input_schema": schema.model_json_schema(),
        }
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit"},
        )
        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            # Most often the model hit max_tokens before emitting the tool call.
            raise RuntimeError(
                f"no structured output (stop_reason={resp.stop_reason}); raise max_tokens"
            )
        usage = {
            "tokens_in": resp.usage.input_tokens,
            "tokens_out": resp.usage.output_tokens,
        }
        return schema.model_validate(block.input), usage

    def gemini(self, model, system, user, schema: type[T], max_tokens):
        """Call Gemini with a Pydantic response schema."""
        resp = self.client.models.generate_content(
            model=model,
            contents=f"{system}\n\n{user}",
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
                "max_output_tokens": max_tokens,
            },
        )
        meta = resp.usage_metadata
        usage = {
            "tokens_in": getattr(meta, "prompt_token_count", 0),
            "tokens_out": getattr(meta, "candidates_token_count", 0),
        }
        parsed = (
            resp.parsed
            if isinstance(resp.parsed, schema)
            else schema.model_validate_json(resp.text)
        )
        return parsed, usage


llm = LLM()
