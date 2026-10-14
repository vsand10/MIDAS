import { useState } from "react";
import "./LoginPage.css";
import MidasLogo from "../../assets/midas-logo.svg"



export default function LoginPage({ onLogin, onForgotPassword, onCreateAccount}){
    const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
 
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
 
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }
 
    try {
      setLoading(true);
      await onLogin?.({ email: email.trim(), password });
    } catch (err) {
      setError(err?.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }


return (
    <main className="login">
      <div className="login__container">
        <div className="login__logo">
          <img src={MidasLogo} alt="" className="login__logo-img" />
        </div>
 
        <form className="login__form" onSubmit={handleSubmit} noValidate>
          <label className="visually-hidden" htmlFor="login-email">
            E-mail
          </label>
          <input
            id="login-email"
            className="login__input"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="E-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
          />
 
          <label className="visually-hidden" htmlFor="login-password">
            Password
          </label>
          <div className="login__password">
            <input
              id="login-password"
              className="login__input"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
            <button
              type="button"
              className="login__toggle"
              onClick={() => setShowPassword((s) => !s)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
 
          <button type="button" className="login__forgot" onClick={onForgotPassword}>
            Forgot Password?
          </button>
 
          {error && (
            <p className="login__error" role="alert">
              {error}
            </p>
          )}
 
          <button type="submit" className="login__btn login__btn--primary" disabled={loading}>
            {loading ? "Logging in…" : "Log In"}
          </button>
          <button
            type="button"
            className="login__btn"
            onClick={onCreateAccount}
            disabled={loading}
          >
            Create Account
          </button>
        </form>
      </div>
    </main>
  );
}