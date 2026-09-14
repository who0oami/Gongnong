import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useUser } from "../state/UserContext";

// Wraps a group of routes in App.tsx and redirects to /login when signed out, remembering the
// page the user was headed to so LoginPage can send them back after a successful login.
export default function RequireAuth() {
  const { isAuthenticated } = useUser();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
