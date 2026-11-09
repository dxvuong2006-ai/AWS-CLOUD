import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { isAllowedRole } from "../utils/roles";

export default function ProtectedRoute({ roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page">Đang xác thực...</div>;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (!isAllowedRole(user.role, roles)) return <Navigate to="/forbidden" replace />;
  return <Outlet />;
}
