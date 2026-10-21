import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/Login/LoginPage";
import SignUpPage from "./pages/SignupPage/SignupPage";
import HomePage from "./pages/HomePage/HomePage";
import ForgotPasswordPage from "./pages/ForgotPassword/ForgotPassword";
import SearchPage from "./pages/Search/SearchPage";
import StockDetailPage from "./pages/StockDetail/StockDetailPage";
import AppLayout from "./components/Applayout";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";
import { signUp, logIn, logOut, resetPassword } from "./auth/authService";
import WatchlistPage from "./pages/WatchList/WatchListPage";

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

// Temporary Profile screen: 
function ProfileRoute() {
  const navigate = useNavigate();
  return (
    <main className="page">
      <h1 className="page-title">Profile</h1>
      <div className="card empty-state">The full Profile screen is coming soon.</div>
      <button
        type="button"
        className="btn btn--outline"
        style={{ width: "100%", marginTop: 16 }}
        onClick={async () => {
          await logOut();
          navigate("/");
        }}
      >
        Log Out
      </button>
    </main>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Logged-out screens (no bottom nav) */}
          <Route path="/" element={<LoginRoute />} />
          <Route path="/signup" element={<SignUpRoute />} />
          <Route path="/forgot-password" element={<ForgotPasswordRoute />} />

          {/* Logged-in screens: must be signed in, and all get the bottom nav */}
          <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route path="/home" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/stock/:symbol" element={<StockDetailPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/profile" element={<ProfileRoute />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}