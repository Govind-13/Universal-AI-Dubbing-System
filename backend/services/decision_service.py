"""
Optional TypeSafe/Jev structured-decision layer.

Isolated from the rest of the pipeline: nothing here is imported by default
behavior. Call sites in main.py / translation_service.py obtain a provider via
create_decision_provider() and must treat every method call as fallible —
network errors, timeouts, and malformed responses are caught by
TypeSafeDecisionProvider itself and surfaced as None/the safe default, so
callers never need their own try/except around a decision call.

When TYPESAFE_ENABLED is unset/false, or TYPESAFE_API_KEY is missing,
create_decision_provider() returns NoopDecisionProvider, whose answers are
chosen to reproduce today's existing behavior exactly (see each method's
docstring). This guarantees zero behavior change with the feature off.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TYPESAFE_API_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = "jev-latest"
TYPESAFE_TIMEOUT_SECONDS = 15


class DecisionProvider(ABC):
    @abstractmethod
    async def evaluate_translation_quality(self, signals: dict) -> str:
        """Returns "ACCEPT" | "RETRY" | "HUMAN_REVIEW"."""
        raise NotImplementedError

    @abstractmethod
    async def route_pipeline_failure(self, context: dict) -> str:
        """Returns "retry" | "fallback" | "continue" | "stop" | "human_review"."""
        raise NotImplementedError

    @abstractmethod
    async def resolve_language(self, code: str) -> Optional[str]:
        """Returns a known LANGUAGE_ALIASES key, or None if undecidable."""
        raise NotImplementedError


class NoopDecisionProvider(DecisionProvider):
    """Reproduces today's pre-Jev behavior exactly. Used when the feature
    is disabled, unconfigured, or as the fallback when Jev itself fails."""

    async def evaluate_translation_quality(self, signals: dict) -> str:
        # Today: any structural validation failure hard-fails the job.
        # Callers must treat this as "do not override — re-raise the original error."
        return "HUMAN_REVIEW"

    async def route_pipeline_failure(self, context: dict) -> str:
        # Today: every exception marks the job "Failed" with no retry.
        return "stop"

    async def resolve_language(self, code: str) -> Optional[str]:
        # Today: unrecognized codes pass through unchanged.
        return None


class TypeSafeDecisionProvider(DecisionProvider):
    provider_name = "typesafe"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY is required for the TypeSafe decision provider.")
        self._api_key = api_key
        self._session = requests.Session()

    def _call(self, state: dict, question_id: str, question: dict) -> Optional[dict]:
        try:
            response = self._session.post(
                TYPESAFE_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "state": state,
                    "model": TYPESAFE_MODEL,
                    "questions": {question_id: question},
                },
                timeout=TYPESAFE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("answers", {}).get(question_id)
        except Exception as e:
            logger.warning("[TypeSafe] Decision call failed, falling back to safe default: %s", e)
            return None

    async def evaluate_translation_quality(self, signals: dict) -> str:
        answer = await asyncio.to_thread(
            self._call,
            signals,
            "translation_quality",
            {
                "type": "choice",
                "instructions": (
                    "Given the translated segment and the structural validation errors "
                    "found in it, decide the right next action for this dubbing job."
                ),
                "criteria": {
                    "ACCEPT": "The validation errors are cosmetic/non-blocking; proceed with this translation as-is.",
                    "RETRY": "The translation should be regenerated once and re-validated before deciding further.",
                    "HUMAN_REVIEW": "The translation has real issues but is usable; flag it for a person to check rather than blocking output.",
                },
            },
        )
        if answer and answer.get("type") == "choice" and answer.get("choice") in {
            "ACCEPT", "RETRY", "HUMAN_REVIEW",
        }:
            return answer["choice"]
        return await NoopDecisionProvider().evaluate_translation_quality(signals)

    async def route_pipeline_failure(self, context: dict) -> str:
        answer = await asyncio.to_thread(
            self._call,
            context,
            "pipeline_failure",
            {
                "type": "choice",
                "instructions": (
                    "A video dubbing job failed at a given stage with a given error. "
                    "Decide the right next action. Only 'retry' is currently acted on "
                    "as a full job restart; 'fallback' and 'continue' are treated the "
                    "same as 'stop' by the caller today."
                ),
                "criteria": {
                    "retry": "The failure looks transient (network blip, timeout); restarting the whole job from scratch is likely to succeed.",
                    "fallback": "The failing stage is non-essential; a degraded output could still be produced.",
                    "continue": "The failure does not need to block job completion.",
                    "stop": "The failure is a real dead-end; do not retry.",
                    "human_review": "The failure is unusual enough that a person should look at it before any retry.",
                },
            },
        )
        if answer and answer.get("type") == "choice" and answer.get("choice") in {
            "retry", "fallback", "continue", "stop", "human_review",
        }:
            return answer["choice"]
        return await NoopDecisionProvider().route_pipeline_failure(context)

    async def resolve_language(self, code: str) -> Optional[str]:
        from services.translation_service import LANGUAGE_ALIASES

        options = sorted(LANGUAGE_ALIASES.keys())
        answer = await asyncio.to_thread(
            self._call,
            {"unrecognized_code": code},
            "resolve_language",
            {
                "type": "choice",
                "instructions": (
                    f"The target language code '{code}' is not recognized. "
                    "Pick the closest known language it most likely refers to."
                ),
                "criteria": {opt: opt for opt in options},
            },
        )
        if answer and answer.get("type") == "choice" and answer.get("choice") in options:
            confidence = answer.get("confidence")
            if confidence is None or confidence >= 0.6:
                return answer["choice"]
        return None


def create_decision_provider() -> DecisionProvider:
    enabled = (os.getenv("TYPESAFE_ENABLED", "false") or "").strip().lower() == "true"
    api_key = os.getenv("TYPESAFE_API_KEY")
    if not enabled or not api_key:
        return NoopDecisionProvider()
    return TypeSafeDecisionProvider(api_key)
