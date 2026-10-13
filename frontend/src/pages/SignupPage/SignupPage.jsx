import { useState } from "react";
import "./SignupPage.css";

const EMPTY = { firstName: "", lastName: "", email: "", password: "" };
const MIN_PASSWORD = 8;

export default function SignUpPage({ onSignUp, onBack }) {
  const [form, setForm] = useState(EMPTY);
  const [emailError, setEmailError] = useState("");
  const [formError, setFormError] = useState("");      // NEW
  const [submitting, setSubmitting] = useState(false); // NEW

  const allFilled =
    form.firstName.trim() && form.lastName.trim() && form.email.trim() && form.password;
  const passwordTooShort = form.password.length > 0 && form.password.length < MIN_PASSWORD;
  const canSubmit = allFilled && !passwordTooShort;

  const update = (field) => (e) => {
    setForm((f) => ({ ...f, [field]: e.target.value }));
    if (field === "email") setEmailError("");
  };

  // CHANGED: async, awaits onSignUp, shows errors thrown by signUp()
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit || submitting) return;

    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) {
      setEmailError("Please enter a valid email address.");
      return;
    }

    setFormError("");
    setSubmitting(true);
    try {
      await onSignUp?.({
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        email: form.email.trim(),
        password: form.password,
      });
    } catch (err) {
      if (err.field === "email") setEmailError(err.message);
      else setFormError(err.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="signup">
      <div className="signup__container">
        <header className="signup__header">
          <button type="button" className="signup__back" onClick={onBack} aria-label="Back">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <h1 className="signup__title">Sign-Up</h1>
        </header>

        <form className="signup__form" onSubmit={handleSubmit} noValidate>
          <Field id="su-first" label="First Name" autoComplete="given-name"
            value={form.firstName} onChange={update("firstName")} />
          <Field id="su-last" label="Last Name" autoComplete="family-name"
            value={form.lastName} onChange={update("lastName")} />
          <Field id="su-email" label="E-mail" type="email" inputMode="email" autoComplete="email"
            value={form.email} onChange={update("email")} error={emailError} />
          <Field id="su-password" label="Password" type="password" autoComplete="new-password"
            value={form.password} onChange={update("password")}
            hint={`At least ${MIN_PASSWORD} characters`} hintIsError={passwordTooShort} />

          {/* CHANGED: disabled while submitting */}
          <button type="submit" className="signup__btn" disabled={!canSubmit || submitting}>
            {submitting ? "Creating account..." : "Continue"}
          </button>
          {/* NEW: general error (this class already exists in SignUpPage.css) */}
          {formError && <p className="signup__error" role="alert">{formError}</p>}
        </form>
      </div>
    </main>
  );
}

function Field({ id, label, error, hint, hintIsError, ...inputProps }) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="signup__field">
      <label className="visually-hidden" htmlFor={id}>{label}</label>
      <input
        id={id}
        className={`signup__input${error ? " signup__input--error" : ""}`}
        placeholder={label}
        aria-invalid={!!error}
        aria-describedby={describedBy}
        {...inputProps}
      />
      {error ? (
        <p id={`${id}-error`} className="signup__field-error" role="alert">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className={`signup__hint${hintIsError ? " signup__hint--error" : ""}`}>{hint}</p>
      ) : null}
    </div>
  );
}