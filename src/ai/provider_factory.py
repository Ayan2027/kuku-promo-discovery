"""Provider factory.

Swapping the model should be a one-line environment change:

    AI_PROVIDER=local
    AI_PROVIDER=gemini

Both providers expose the same tiny interface: ``analyze(prompt)`` returns a
dict or ``None``, and ``status()`` returns a JSON-serialisable run summary.
"""

from __future__ import annotations

import os

from src.ai.gemini_provider import GeminiProvider


class LocalHeuristicProvider:
    """No-network provider used for reproducible local runs."""

    def __init__(self):
        self.requests_used = 0

    def analyze(self, prompt: str):
        self.requests_used += 0
        return None

    def status(self):
        return {
            "enabled": False,
            "provider": "local-heuristic",
            "requests_used": 0,
            "max_requests": 0,
            "remaining_requests": 0,
            "model": "none (deterministic fallback)",
        }


def create_provider(mode: str | None = None):
    mode = (mode or os.getenv("AI_PROVIDER", "auto")).strip().lower()

    if mode == "local":
        return LocalHeuristicProvider()

    if mode in {"gemini", "auto"}:
        return GeminiProvider()

    raise ValueError(
        f"Unknown AI_PROVIDER={mode!r}. Use 'local', 'gemini' or 'auto'."
    )
