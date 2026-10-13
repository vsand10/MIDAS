import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null; // wait for Firebase before deciding
  return user ? children : <Navigate to="/" replace />; // "/" is your login route
}