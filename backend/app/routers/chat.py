"""MIDAS Chat endpoint (CHAT-01).

    POST /api/chat      (login required)
    body:  {"message": "Why is it down today?",
            "symbol": "AAPL",                      # optional
            "history": [{"role": "user", "text": "..."},
                        {"role": "assistant", "text": "..."}]}   # optional, oldest first
    reply: {"reply": "..."}

The backend keeps no chat history: the app sends the conversation each time.
"""

import logging
import time
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from app.deps import get_current_user
from app.services import chat_service, gemini

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000
MAX_HISTORY_ITEMS = 40

# Each user may send this many messages per minute. Gemini's free plan allows
# only about 10 requests a minute for the WHOLE app, so one person can't use it all up.
MESSAGES_PER_MINUTE = 6
_recent_messages: dict[str, deque[float]] = defaultdict(deque)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: Annotated[str, StringConstraints(max_length=8000)]


class ChatRequest(BaseModel):
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]
    symbol: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z.\-]{0,9}$")] | None = None
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


class ChatReply(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatReply)
def chat(body: ChatRequest, user: dict = Depends(get_current_user)) -> ChatReply:
    _check_rate_limit(user["uid"])

    symbol = body.symbol.upper() if body.symbol else None
    history = [turn.model_dump() for turn in body.history]
    try:
        reply = chat_service.reply_to(body.message, history, symbol)
    except gemini.GeminiNotConfiguredError as err:
        log.error("MIDAS Chat is not configured: %s", err)
        raise HTTPException(503, "The AI assistant isn't set up yet.") from err
    except gemini.GeminiRateLimitedError as err:
        raise HTTPException(
            429, "The AI assistant is busy right now. Please try again in a minute."
        ) from err
    except gemini.GeminiError as err:
        log.warning("MIDAS Chat failed: %s", err)
        raise HTTPException(502, "The AI assistant couldn't answer. Please try again.") from err
    return ChatReply(reply=reply)


def _check_rate_limit(uid: str) -> None:
    now = time.monotonic()
    sent = _recent_messages[uid]
    while sent and now - sent[0] > 60:
        sent.popleft()
    if len(sent) >= MESSAGES_PER_MINUTE:
        raise HTTPException(429, "You're sending messages too quickly. Please wait a moment.")
    sent.append(now)