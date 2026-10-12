import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/Login/LoginPage";
import SignUpPage from "./pages/SignupPage/SignupPage";
import HomePage from "./pages/HomePage/HomePage";
import ForgotPasswordPage from "./pages/ForgotPassword/ForgotPassword";

// Authentication isn't connected yet: Log In and Continue go straight to Home.
// Replace the TODOs once the login and sign up APIs exist.

function LoginRoute() {
  const navigate = useNavigate();
  return (
    <LoginPage
      onLogin={() => navigate("/home")} // TODO: check credentials with the API first
      onForgotPassword={() => navigate("/forgot-password")}
      onCreateAccount={() => navigate("/signup")}
      
    />
  );
}

function SignUpRoute() {
  const navigate = useNavigate();
  return (
    <SignUpPage
      onSignUp={() => navigate("/home")} // TODO: create the account with the API first
      onBack={() => navigate("/")}
    />
  );
}
function ForgotPasswordRoute() {
  const navigate = useNavigate();
  return (
    <ForgotPasswordPage
      onSendLink={() => navigate("/")} // TODO: send the reset email first
      onBack={() => navigate("/")}
      onLogin={() => navigate("/")}
    />
  );
}

function HomeRoute() {
  const navigate = useNavigate();
  return <HomePage onLogOut={() => navigate("/")} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginRoute />} />
        <Route path="/signup" element={<SignUpRoute />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/home" element={<HomeRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}