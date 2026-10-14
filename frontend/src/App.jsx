import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/Login/LoginPage";
import SignUpPage from "./pages/SignupPage/SignupPage";
import HomePage from "./pages/HomePage/HomePage";
import ForgotPasswordPage from "./pages/ForgotPassword/ForgotPassword";



function LoginRoute() {
  const navigate = useNavigate();
  return (
    <LoginPage
      onLogin={() => navigate("/home")} 
      onForgotPassword={() => navigate("/forgot-password")}
      onCreateAccount={() => navigate("/signup")}
      
    />
  );
}

function SignUpRoute() {
  const navigate = useNavigate();
  return (
    <SignUpPage
      onSignUp={() => navigate("/home")} 
      onBack={() => navigate("/")}
    />
  );
}
function ForgotPasswordRoute() {
  const navigate = useNavigate();
  return (
    <ForgotPasswordPage
      onSendLink={() => navigate("/")} 
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
