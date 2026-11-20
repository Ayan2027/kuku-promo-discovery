
import json
import time
import logging

from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self):
        self.client = None
        self.enabled = False
        self.requests_used = 0

        self.max_requests = int(
            __import__("os").getenv(
                "GEMINI_MAX_REQUESTS_PER_RUN", "10"
            )
        )

        self.delay = float(
            __import__("os").getenv(
                "GEMINI_REQUEST_DELAY_SECONDS", "5"
            )
        )

        provider_mode = __import__("os").getenv(
            "AI_PROVIDER", "auto"
        ).lower()

        if provider_mode == "local":
            logger.info("Local-only AI mode enabled.")
            return

        api_key = settings.GEMINI_API_KEY

        if not api_key:
            logger.info(
                "Gemini API key missing. Using local fallback."
            )
            return

        try:
            from google import genai

            self.client = genai.Client(
                api_key=api_key
            )

            self.enabled = True

            logger.info("Gemini provider initialized.")

        except Exception as exc:
            logger.error(
                "Gemini initialization failed: %s", exc
            )

            self.enabled = False

    def analyze(self, prompt: str) -> dict[str, Any] | None:
        """
        Send one request to Gemini.

        Returns parsed JSON or None on failure.
        """

        if not self.enabled:
            return None

        if self.requests_used >= self.max_requests:
            logger.warning(
                "Gemini request budget exhausted."
            )
            return None

        try:
            from google.genai import types

            # Apply delay only after the first request.
            if self.requests_used > 0:
                time.sleep(self.delay)

            self.requests_used += 1

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            if not response.text:
                logger.warning("Gemini returned empty response.")
                return None

            result = json.loads(response.text)

            if not isinstance(result, dict):
                logger.warning(
                    "Gemini response is not a JSON object."
                )
                return None

            return result

        except json.JSONDecodeError:
            logger.exception("Gemini returned malformed JSON.")
            return None

        except Exception as exc:
            logger.error("Gemini request failed: %s", exc)
            return None

    def status(self):
        return {
            "enabled": self.enabled,
            "provider": "gemini",
            "requests_used": self.requests_used,
            "max_requests": self.max_requests,
            "remaining_requests": max(
                0,
                self.max_requests - self.requests_used
            ),
            "model": settings.GEMINI_MODEL,
        }
