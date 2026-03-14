"""Anthropic Claude client with GitLab AI Gateway proxy support."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from forgeproof.config import ForgeProofConfig

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192


class ClaudeClient:
    """Wrapper around the Anthropic SDK that supports GitLab AI Gateway proxy."""

    def __init__(self, config: ForgeProofConfig) -> None:
        self._config = config
        self._client = self._build_client()
        self._call_count = 0

    def _build_client(self) -> anthropic.Anthropic:
        cfg = self._config

        # GitLab AI Gateway mode (production)
        if cfg.anthropic_auth_token:
            extra_headers: dict[str, str] = {}
            if cfg.anthropic_custom_headers:
                try:
                    extra_headers = json.loads(cfg.anthropic_custom_headers)
                except json.JSONDecodeError:
                    # Headers may be in "Key: Value\nKey2: Value2" format
                    for line in cfg.anthropic_custom_headers.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            extra_headers[k.strip()] = v.strip()

            return anthropic.Anthropic(
                api_key=cfg.anthropic_auth_token,
                base_url=cfg.anthropic_base_url,
                default_headers=extra_headers,
            )

        # Local dev mode (direct Anthropic API key)
        if cfg.anthropic_api_key:
            return anthropic.Anthropic(api_key=cfg.anthropic_api_key)

        raise RuntimeError(
            "No Anthropic credentials found. Set ANTHROPIC_API_KEY for local dev "
            "or AI_FLOW_AI_GATEWAY_TOKEN for GitLab Duo."
        )

    @property
    def call_count(self) -> int:
        return self._call_count

    def ask(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
        temperature: float = 0.0,
    ) -> str:
        """Send a single-turn message and return the text response."""
        self._call_count += 1
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        log.info("Claude call #%d (model=%s, prompt_len=%d)", self._call_count, model, len(prompt))
        response = self._client.messages.create(**kwargs)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        log.info("Claude response #%d: %d chars", self._call_count, len(text))
        return text

    def ask_json(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
    ) -> dict[str, Any]:
        """Send a prompt and parse the response as JSON."""
        raw = self.ask(prompt, system=system, model=model, max_tokens=max_tokens)

        # Extract JSON from markdown code blocks if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first and last ``` lines
            start = 1
            end = len(lines) - 1
            if lines[end].strip() == "```":
                text = "\n".join(lines[start:end])
            else:
                text = "\n".join(lines[start:])
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            log.error("Failed to parse Claude response as JSON: %s...", text[:200])
            raise
