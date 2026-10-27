import AppRoutes from "./routes/AppRoutes";
import Navbar from "./components/layout/Navbar";
import { useNavigate } from "react-router-dom";
import "./routes/AppRouter.css";

export default function App() {
  const navigate = useNavigate();

  // TODO: Thay dữ liệu mẫu bằng user lấy từ AuthContext/API.
  // Test với Role khác : TEACHER,ADMIN
  const user = {
    name: "Vương Dũng",
    role: "TEACHER",
  };

  // TODO: Đổi thành TEACHER hoặc ADMIN để thử các sidebar khác.
  const role = user?.role || "STUDENT";

  return (
    <>
      <Navbar
        user={user}
        role={role}
        onLogout={() => {
          // TODO: Xóa token và gọi API logout khi tích hợp đăng nhập.
          navigate("/login");
        }}
      />

      <main className="app-content">
        <AppRoutes />
      </main>
    </>
  );
}
