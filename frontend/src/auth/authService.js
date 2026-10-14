import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
} from "firebase/auth";
import { doc, setDoc, serverTimestamp } from "firebase/firestore";
import { auth, db } from "./firebase";

// Builds an Error whose .field tells a screen which input to show it under.
function fieldError(message, field) {
  const e = new Error(message);
  e.field = field;
  return e;
}

export async function signUp({ firstName, lastName, email, password }) {
  try {
    const cred = await createUserWithEmailAndPassword(auth, email.trim(), password);
    await updateProfile(cred.user, { displayName: `${firstName} ${lastName}` });
    await setDoc(doc(db, "users", cred.user.uid), {
      firstName,
      lastName,
      email: email.trim(),
      createdAt: serverTimestamp(),
    });
    return cred.user;
  } catch (err) {
    if (err.code === "auth/email-already-in-use")
      throw fieldError("An account with this email already exists.", "email");
    if (err.code === "auth/invalid-email")
      throw fieldError("Please enter a valid email address.", "email");
    if (err.code === "auth/weak-password")
      throw new Error("Password is too weak. Use at least 8 characters.");
    if (err.code === "auth/network-request-failed")
      throw new Error("Network error. Check your connection and try again.");
    throw new Error("Something went wrong. Please try again.");
  }
}

export async function logIn({ email, password }) {
  try {
    const cred = await signInWithEmailAndPassword(auth, email.trim(), password);
    return cred.user;
  } catch (err) {
    if (
      ["auth/invalid-credential", "auth/wrong-password", "auth/user-not-found"].includes(err.code)
    )
      throw new Error("Invalid email or password");
    if (err.code === "auth/too-many-requests")
      throw new Error("Too many attempts. Try again later.");
    if (err.code === "auth/network-request-failed")
      throw new Error("Network error. Check your connection and try again.");
    throw new Error("Something went wrong. Please try again.");
  }
}

export function logOut() {
  return signOut(auth);
}

export async function resetPassword(email) {
  try {
    await sendPasswordResetEmail(auth, email.trim());
  } catch (err) {
    if (err.code === "auth/invalid-email")
      throw fieldError("Please enter a valid email address.", "email");
    if (err.code === "auth/too-many-requests")
      throw new Error("Too many attempts. Try again later.");
    if (err.code === "auth/network-request-failed")
      throw new Error("Network error. Check your connection and try again.");
    throw new Error("Something went wrong. Please try again.");
  }
}