"""The only file that talks to Google's Gemini API (CHAT-01).

Settings, in backend/.env:
    GEMINI_API_KEY=...            (free key from https://aistudio.google.com/apikey)
    GEMINI_MODEL=gemini-3.5-flash-lite 

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


def generate(
    system_instruction: str, 
    contents: list[dict],
    *,
    grounded: bool = True,
    json_output: bool = False,
) -> dict:
    """Sends the conversation to Gemini and returns its reply text plus sources.
    
    grounded=True lets Gemini use Google Search (MIDAS Chat). "Why it moved" passes
    grounded=False, because it may only use the news articles MIDAS gives it, and
    json_output=True, which asks for a JSON reply.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not set")
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    config = {
        "temperature": 0.4,
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
    }
    if json_output:
        config["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": config,
    }
    if grounded:
        # Google Search grounding for current information
        payload["tools"] = [{"google_search": {}}]
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
    return {
        "reply": _reply_text(data),
        "sources": _sources(data),
        "citations": _citations(data)
}


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


def _sources(data: dict) -> list[dict]:
    """Get web sources returned by Google Search grounding."""

    candidates = data.get("candidates") or []

    if not candidates:
        return []

    candidate = candidates[0]

    metadata = (
        candidate.get("groundingMetadata")
        or {}
    )

    chunks = (
        metadata.get("groundingChunks")
        or []
    )

    sources = []
    seen_urls = set()

    for chunk in chunks:
        web = (
            chunk.get("web")
            if isinstance(chunk, dict)
            else None
        )

        if not isinstance(web, dict):
            continue

        url = str(
            web.get("uri") or ""
        ).strip()

        if not url:
            continue

        # Prevent duplicate sources
        if url in seen_urls:
            continue

        seen_urls.add(url)

        title = str(
            web.get("title") or "Source"
        ).strip()

        sources.append(
            {
                "title": title or "Source",
                "url": url,
            }
        )

    return sources

def _citations(data: dict) -> list[dict]:
    """Which web sources back which part of the reply (Google's groundingSupports).

    Each item is {"text": the part of the reply, "urls": the sources that back it}.
    Google numbers its sources in its own order, so this reads the original list,
    before _sources() removes duplicates.
    """
    candidates = data.get("candidates") or []
    if not candidates:
        return []
    metadata = candidates[0].get("groundingMetadata") or {}

    urls = []
    for chunk in metadata.get("groundingChunks") or []:
        web = chunk.get("web") if isinstance(chunk, dict) else None
        urls.append(str(web.get("uri") or "").strip() if isinstance(web, dict) else "")

    citations = []
    for support in metadata.get("groundingSupports") or []:
        if not isinstance(support, dict):
            continue
        segment = support.get("segment")
        text = str(segment.get("text") or "") if isinstance(segment, dict) else ""
        found = [
            urls[i]
            for i in support.get("groundingChunkIndices") or []
            if isinstance(i, int) and 0 <= i < len(urls) and urls[i]
        ]
        if text and found:
            citations.append({"text": text, "urls": found})
    return citations
