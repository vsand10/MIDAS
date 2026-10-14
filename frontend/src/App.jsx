import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/Login/LoginPage";
import SignUpPage from "./pages/SignupPage/SignupPage";
import HomePage from "./pages/HomePage/HomePage";
import ForgotPasswordPage from "./pages/ForgotPassword/ForgotPassword";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";
import { signUp, logIn, logOut, resetPassword } from "./auth/authService";

function LoginRoute() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/home" replace />; // already logged in

  return (
    <LoginPage
      onLogin={async (credentials) => {
        await logIn(credentials); // throws "Invalid email or password" on failure
        navigate("/home");
      }}
      onForgotPassword={() => navigate("/forgot-password")}
      onCreateAccount={() => navigate("/signup")}
    />
  );
}

function SignUpRoute() {
  const navigate = useNavigate();
  return (
    <SignUpPage
      onSignUp={async (data) => {
        await signUp(data); // throws on failure, so navigate below is skipped
        navigate("/home");
      }}
      onBack={() => navigate("/")}
    />
  );
}

function ForgotPasswordRoute() {
  const navigate = useNavigate();
  return (
    <ForgotPasswordPage
      onSendLink={(email) => resetPassword(email)} // page shows the confirmation itself
      onBack={() => navigate("/")}
      onLogin={() => navigate("/")}
    />
  );
}

function HomeRoute() {
  const navigate = useNavigate();
  return (
    <HomePage
      onLogOut={async () => {
        await logOut();
        navigate("/");
      }}
    />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LoginRoute />} />
          <Route path="/signup" element={<SignUpRoute />} />
          <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
          <Route
            path="/home"
            element={
              <RequireAuth>
                <HomeRoute />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}