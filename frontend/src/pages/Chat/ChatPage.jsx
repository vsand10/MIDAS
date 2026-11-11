import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import midasLogo from "../../assets/midas-logo.svg";
import { sendChatMessage } from "../../services/chatservice";
import "../../App.css";
import "./ChatPage.css";

const MAX_MESSAGE_CHARS = 1000; // same limit as the backend

// Keeps each conversation while the app stays open, so going Back and
// returning doesn't lose it. Cleared when the page is reloaded.
const savedChats = new Map();

let messageCount = 0;
const newId = () => `m${Date.now()}-${messageCount++}`;

/**
 * MIDAS Chat screen.
 *   /stock/:symbol/chat   chat about one stock
 *   /chat                 general chat
 */
export default function ChatPage() {
  const { symbol } = useParams();
  const sym = symbol ? symbol.toUpperCase() : null;
  // key: start with the right conversation if the stock in the address changes
  return <Chat key={sym ?? "general"} sym={sym} />;
}

function Chat({ sym }) {
  const chatKey = sym ?? "general";
  const navigate = useNavigate();
  const location = useLocation();
  const name = location.state?.name || sym;

  // Each message: { id, role: "user" | "assistant", text, sources? }
  const [messages, setMessages] = useState(() => savedChats.get(chatKey) ?? []);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const endRef = useRef(null);
  const inputRef = useRef(null);
  const requestRef = useRef(null);

  useEffect(() => {
    savedChats.set(chatKey, messages);
  }, [chatKey, messages]);

  // Keep the newest message in view
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending, error]);

  // Cancel a request that's still running when the user leaves the screen
  useEffect(() => () => requestRef.current?.abort(), []);

  /** Asks the backend to answer the last message in `all` (which must be the user's). */
  const requestReply = async (all) => {
    const last = all[all.length - 1];
    const controller = new AbortController();
    requestRef.current = controller;
    setSending(true);
    setError("");
    try {
      const result = await sendChatMessage({
        message: last.text,
        history: all.slice(0, -1).map(({ role, text }) => ({ role, text })),
        symbol: sym,
        signal: controller.signal,
      });
      setMessages((current) => [...current, { id: newId(), role: "assistant", text: result.reply, sources: result.sources }]);
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message || "The AI assistant couldn't answer. Please try again.");
      }
    } finally {
      if (requestRef.current === controller) setSending(false);
    }
  };

  const send = (text) => {
    const trimmed = text.trim().slice(0, MAX_MESSAGE_CHARS);
    if (!trimmed || sending) return;
    const next = [...messages, { id: newId(), role: "user", text: trimmed }];
    setMessages(next);
    setDraft("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    requestReply(next);
  };

  const retry = () => {
    if (!sending && messages.length) requestReply(messages);
  };

  const startNewChat = () => {
    setMessages([]);
    setError("");
    inputRef.current?.focus();
  };

  const onDraftChange = (e) => {
    setDraft(e.target.value);
    // Grow the box with the text, up to a few lines
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const onKeyDown = (e) => {
    // Enter sends; Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(draft);
    }
  };

  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate(sym ? `/stock/${sym}/why` : "/home");
  };

  const openSources = (messageIndex) => {
    const message = messages[messageIndex];

    navigate("/chat/sources", {
      state: {
        sources: message.sources || [],
        question:
          messageIndex > 0 && messages[messageIndex - 1]?.role === "user"
            ? messages[messageIndex - 1].text
            : "",
      },
    });
  };
  const greeting = sym
    ? `Hi! I'm MIDAS. Ask me anything about ${name}, like what the company does or what's been in the news.`
    : "Hi! I'm MIDAS. Ask me about a stock, the market or an investing term.";
  const suggestions = sym
    ? [`What does ${name} do?`, `What's in the news for ${name}?`, "What is a P/E ratio?"]
    : ["What moves stock prices?", "What is a P/E ratio?", "What is an index fund?"];

  return (
    <div className="chat">
      <header className="chat__header">
        <div className="chat__header-row">
          <button type="button" className="back-btn" onClick={goBack}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                d="M15 5l-7 7 7 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back
          </button>
          {messages.length > 0 && (
            <button type="button" className="chat__new" onClick={startNewChat} disabled={sending}>
              New chat
            </button>
          )}
        </div>
        <h1 className="chat__title">MIDAS Chat</h1>
      </header>

      <div className="chat__messages" role="log" aria-live="polite" aria-label="Conversation">
        <AssistantMessage>{greeting}</AssistantMessage>

        {messages.length === 0 && (
          <div className="chat__suggestions">
            {suggestions.map((question) => (
              <button
                key={question}
                type="button"
                className="chat__suggestion"
                onClick={() => send(question)}
                disabled={sending}
              >
                {question}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, index) =>
          m.role === "user" ? (
            <div className="chat__row chat__row--user" key={m.id}>
              <p className="chat__bubble chat__bubble--user">{m.text}</p>
            </div>
          ) : (
            <AssistantMessage key={m.id}>
              {cleanReply(m.text)}

              {m.sources?.length > 0 && (
                <button
                  type="button"
                  className="chat__sources"
                  onClick={() => openSources(index)}
                >
                  Sources ({m.sources.length})
                </button>
              )}
            </AssistantMessage>
          )
        )}

        {sending && (
          <AssistantMessage>
            <span className="chat__typing" role="status" aria-label="MIDAS is typing">
              <span />
              <span />
              <span />
            </span>
          </AssistantMessage>
        )}

        {error && (
          <div className="chat__error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form
        className="chat__composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <label htmlFor="chat-input" className="visually-hidden">
          Message
        </label>
        <textarea
          id="chat-input"
          ref={inputRef}
          className="chat__input"
          rows={1}
          placeholder="Chat here..."
          maxLength={MAX_MESSAGE_CHARS}
          enterKeyHint="send"
          value={draft}
          onChange={onDraftChange}
          onKeyDown={onKeyDown}
        />
        <button
          type="submit"
          className="chat__send"
          disabled={!draft.trim() || sending}
          aria-label="Send message"
        >
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <path
              d="M21 3L10 14M21 3l-7 18-4-7-7-4 18-7z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>
      <p className="chat__note">AI answers can be wrong and aren&apos;t financial advice.</p>
    </div>
  );
}

function AssistantMessage({ children }) {
  return (
    <div className="chat__row chat__row--assistant">
      <img className="chat__avatar" src={midasLogo} alt="MIDAS" />
      <div className="chat__bubble chat__bubble--assistant">{children}</div>
    </div>
  );
}

/** The model is told to answer in plain text; this tidies up any Markdown that slips through. */
function cleanReply(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^(\s*)[*•]\s+/gm, "$1- ")
    .trim();
}