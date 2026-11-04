import { useState } from "react";
import AppRoutes from "./routes/AppRoutes";
import Navbar from "./components/layout/Navbar";
import { useNavigate } from "react-router-dom";
import "./routes/AppRouter.css";

export default function App() {
  const navigate = useNavigate();
  const [navbarCollapsed, setNavbarCollapsed] = useState(false);

  const user = {
    name: "Vương Dũng",
    role: "STUDENT",
  };

  const role = user?.role || "STUDENT";

  return (
    <div className={`app-shell ${navbarCollapsed ? "app-shell--collapsed" : ""}`}>
      <Navbar
        user={user}
        role={role}
        collapsed={navbarCollapsed}
        onToggle={() => setNavbarCollapsed((collapsed) => !collapsed)}
        onLogout={() => {
          navigate("/login");
        }}
      />

      <main className="app-content">
        <AppRoutes />
      </main>
    </div>
  );
}