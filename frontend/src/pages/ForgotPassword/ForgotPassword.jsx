import { useState } from "react";
import "./ForgotPassword.css";

/**
 * MIDAS – Forgot Password screen (UI only, no reset logic yet)
 *
 * Props:
 *  - onSendLink(email)   called when "Send Reset Link" is tapped
 *  - onBack()            back arrow
 *  - onLogin()           "Log in" link at the bottom
 */
export default function ForgotPasswordPage({ onSendLink, onBack, onLogin }) {
  const [email, setEmail] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSendLink?.(email.trim());
  };

  return (
    <main className="forgot">
      <div className="forgot__container">
        <header className="forgot__header">
          <button type="button" className="forgot__back" onClick={onBack}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Back
          </button>
        </header>

        <div className="forgot__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="40" height="40">
            <rect x="5" y="10.5" width="14" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
            <path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <circle cx="12" cy="15.5" r="1.4" fill="currentColor" />
          </svg>
        </div>

        <h1 className="forgot__title">Forgot Password</h1>
        <p className="forgot__text">
          Enter the email associated with your account and we&apos;ll send a link to reset your
          password.
        </p>

        <form className="forgot__form" onSubmit={handleSubmit} noValidate>
          <label className="forgot__label" htmlFor="forgot-email">
            E-mail
          </label>
          <input
            id="forgot-email"
            className="forgot__input"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="johndoe@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <button type="submit" className="forgot__btn" disabled={!email.trim()}>
            Send Reset Link
          </button>
        </form>

        <p className="forgot__footer">
          Remember your password?{" "}
          <button type="button" className="forgot__link" onClick={onLogin}>
            Log in
          </button>
        </p>
      </div>
    </main>
  );
}