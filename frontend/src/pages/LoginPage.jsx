import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homeForRole } from "../utils/roles";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  if (loading) return <div className="page">Đang xác thực...</div>;
  const from = location.state?.from;
  const returnTo = typeof from === "string" && from.startsWith("/") &&
    !from.startsWith("//") && from !== "/login" && from !== "/forbidden"
    ? from : homeForRole(user?.role);
  if (user) return <Navigate to={returnTo} replace />;

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(err.status === 401
        ? "Email hoặc mật khẩu không đúng."
        : err.status === 422
          ? "Vui lòng kiểm tra email và mật khẩu."
          : "Không đăng nhập được. Vui lòng thử lại.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="page" style={{ maxWidth: 460, margin: "60px auto" }}>
      <h1>Đăng nhập LearnCloud</h1>
      <form className="card" onSubmit={submit}>
        <label htmlFor="login-email">Email</label>
        <input id="login-email" type="email" autoComplete="username" required
          value={email} onChange={(e) => setEmail(e.target.value)}
          style={{ display: "block", width: "100%", margin: "8px 0 16px" }} />
        <label htmlFor="login-password">Mật khẩu</label>
        <input id="login-password" type="password" autoComplete="current-password" required
          value={password} onChange={(e) => setPassword(e.target.value)}
          style={{ display: "block", width: "100%", margin: "8px 0 16px" }} />
        {error && <p role="alert" style={{ color: "var(--error)" }}>{error}</p>}
        <button className="btn-primary" disabled={submitting}>
          {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
      </form>
    </main>
  );
}
