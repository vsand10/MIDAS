/**
 * MIDAS Chat service: sends a message to the backend, which asks Gemini.
 *
 * The Gemini API key lives ONLY in the backend. Never call Gemini from the
 * browser, or anyone could copy the key out of the app.
 */
import { getAuth } from "firebase/auth";

const API_BASE = "/api"; // FastAPI backend (proxied by Vite)
const MAX_HISTORY_TURNS = 20; // the backend only uses the most recent turns anyway

/**
 * @param {Object} options
 * @param {string} options.message              what the user just typed
 * @param {{role: "user"|"assistant", text: string}[]} [options.history]  earlier turns, oldest first
 * @param {string} [options.symbol]             stock being discussed, e.g. "AAPL"
 * @param {AbortSignal} [options.signal]        lets the screen cancel the request
 * @returns {Promise<string>} the assistant's reply
 */
export async function sendChatMessage({ message, history = [], symbol, signal }) {
  const headers = { "Content-Type": "application/json" };
  const token = await getLoginToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers,
      signal,
      body: JSON.stringify({
        message,
        symbol: symbol || null,
        history: history.slice(-MAX_HISTORY_TURNS),
      }),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error("Can't reach MIDAS. Check your connection and try again.");
  }

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    if (res.status === 401) throw new Error("Please log in again to keep chatting.");
    // The backend sends a ready-to-show message in "detail" (e.g. "The AI assistant is busy...")
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "The AI assistant couldn't answer. Please try again."
    );
  }
  if (typeof data?.reply !== "string" || !data.reply.trim()) {
    throw new Error("The AI assistant couldn't answer. Please try again.");
  }
  return data.reply;
}

/** Firebase login token for the signed-in user (null if not signed in) */
async function getLoginToken() {
  try {
    const user = getAuth().currentUser;
    return user ? await user.getIdToken() : null;
  } catch {
    return null;
  }
}