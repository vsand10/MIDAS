import { auth } from "../auth/firebase";

// Calls the FastAPI backend (Vite forwards /api to it) with the user's Firebase token
export async function apiFetch(path, options = {}) {
  await auth.authStateReady(); // wait until Firebase has restored the session
  const user = auth.currentUser;
  const token = user ? await user.getIdToken() : null;

  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}