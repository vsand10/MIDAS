"""The only file that talks to Google's Gemini API (CHAT-01).

Settings, in backend/.env:
    GEMINI_API_KEY=...            (free key from https://aistudio.google.com/apikey)
    GEMINI_MODEL=gemini-3.8-flash (optional; change here if Google retires the model)

Gemini has no memory between requests, so every call sends the whole
conversation: a list of turns, each {"role": "user" | "model", "parts": [{"text": ...}]}.
"""

import logging
import os

import httpx

DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 30
MAX_OUTPUT_TOKENS = 2048

log = logging.getLogger(__name__)


class GeminiError(Exception):
    """Something went wrong talking to Gemini."""


class GeminiNotConfiguredError(GeminiError):
    """No API key, a rejected key, or a model name Google doesn't recognise."""


class GeminiRateLimitedError(GeminiError):
    """The free plan's per-minute or per-day limit was hit, or Gemini is overloaded."""


class GeminiBlockedError(GeminiError):
    """Gemini refused to answer (its safety filters blocked the question or the reply)."""


def _post(url: str, headers: dict, payload: dict) -> httpx.Response:
    """The one line that goes over the network. Tests replace this function."""
    return httpx.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)


def generate(system_instruction: str, contents: list[dict]) -> str:
    """Sends the conversation to Gemini and returns its reply as plain text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not set")
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": MAX_OUTPUT_TOKENS},
    }
    try:
        # The key goes in a header, never in the URL, so it can't end up in logs
        response = _post(API_URL.format(model=model), {"x-goog-api-key": api_key}, payload)
    except httpx.HTTPError as err:
        raise GeminiError("Couldn't reach Gemini") from err

    if response.status_code != 200:
        _raise_for_status(response, model)

    try:
        data = response.json()
    except ValueError as err:
        raise GeminiError("Gemini sent a reply that wasn't JSON") from err
    return _reply_text(data)


def _raise_for_status(response: httpx.Response, model: str) -> None:
    status = response.status_code
    try:
        message = str(response.json().get("error", {}).get("message", ""))
    except (ValueError, AttributeError):
        message = ""
    log.warning("Gemini returned HTTP %s for model %s: %s", status, model, message[:300])

    if status == 429 or status == 503:
        raise GeminiRateLimitedError(message or "Gemini is busy")
    if status in (401, 403) or (status == 400 and "api key" in message.lower()):
        raise GeminiNotConfiguredError("Gemini rejected the API key")
    if status == 404:
        raise GeminiNotConfiguredError(
            f"Gemini doesn't know the model '{model}'. Set GEMINI_MODEL to a current one."
        )
    raise GeminiError(f"Gemini returned HTTP {status}")


def _reply_text(data: dict) -> str:
    """Pulls the answer out of Gemini's response."""
    block_reason = (data.get("promptFeedback") or {}).get("blockReason")
    if block_reason:
        raise GeminiBlockedError(f"Question blocked: {block_reason}")

    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini returned no answer")
    candidate = candidates[0]

    parts = (candidate.get("content") or {}).get("parts") or []
    # Skip "thought" parts: those are the model's private reasoning, not the answer
    text = "".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
    ).strip()

    if not text:
        reason = candidate.get("finishReason")
        if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION", "SPII"):
            raise GeminiBlockedError(f"Reply blocked: {reason}")
        raise GeminiError(f"Gemini returned an empty answer (finishReason={reason})")
    return text