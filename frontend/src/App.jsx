import AppRoutes from "./routes/AppRoutes";
import Navbar from "./components/layout/Navbar";
import { useAuth } from "./context/AuthContext";
import { useNavigate } from "react-router-dom";
import "./routes/AppRouter.css";
import "./styles/student.css";

export default function App() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  if (loading) return <div className="page">Đang xác thực...</div>;
  return (
    <div className={String(user?.role).toUpperCase() === "STUDENT" ? "student-shell" : undefined}>
      {user && <Navbar user={user} role={user.role} onLogout={() => {
        logout();
        navigate("/login", { replace: true });
      }} />}
      <div className={user ? "app-content" : undefined}>
        <AppRoutes />
      </div>
    </div>
  );
}
