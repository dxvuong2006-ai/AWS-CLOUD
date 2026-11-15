import AppRoutes from "./routes/AppRoutes";
import Navbar from "./components/layout/Navbar";
import { useAuth } from "./context/AuthContext";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import "./routes/AppRouter.css";
import "./styles/student.css";

export default function App() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [navbarCollapsed, setNavbarCollapsed] = useState(false);
  if (loading) return <div className="page">Đang xác thực...</div>;
  const isStudent = String(user?.role).toUpperCase() === "STUDENT";
  return (
    <div className={`${isStudent ? "student-shell" : ""} ${navbarCollapsed ? "app-shell--collapsed" : ""}`}>
      {user && <Navbar user={user} role={user.role} onLogout={() => {
        logout();
        navigate("/login", { replace: true });
      }} collapsed={navbarCollapsed} onToggleCollapsed={() => setNavbarCollapsed((collapsed) => !collapsed)} />}
      <div className={user ? "app-content" : undefined}>
        <AppRoutes />
      </div>
    </div>
  );
}
