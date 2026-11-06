import { useState } from "react";
import { Navigate, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { homeForRole } from "../utils/roles";
import "./login.css";
import { AUTH_MOCK } from "../api/auth.api";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

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
        : err.status === 403
          ? "Email chưa được xác minh. Vui lòng xác minh trước khi đăng nhập."
        : err.status === 422
          ? "Vui lòng kiểm tra email và mật khẩu."
          : "Không đăng nhập được. Vui lòng thử lại.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-screen">
      <aside className="login-brand-panel">
        <div className="login-brand"><span aria-hidden="true">L</span>LearnCloud</div>
        <div className="login-brand-copy">
          <h2>Học qua video,<br />ôn đúng chỗ cần ôn.</h2>
          <p>Mỗi bài giảng có transcript, tóm tắt, flashcard và checkpoint — tất cả trong một nơi.</p>
        </div>
      </aside>

      <section className="login-form-panel" aria-labelledby="login-title">
        <div className="login-form-content">
          <h1 id="login-title">Đăng nhập</h1>
          <p className="login-subtitle">Truy cập theo vai trò của bạn.</p>
          <form onSubmit={submit}>
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" autoComplete="username" required
              placeholder="ten@example.com" value={email}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "login-error" : undefined}
              onChange={(event) => { setEmail(event.target.value); setError(""); }} />

            <label htmlFor="login-password">Mật khẩu</label>
            <div className="login-password">
              <input id="login-password" type={showPassword ? "text" : "password"}
                autoComplete="current-password" required placeholder="••••••••••"
                value={password} aria-invalid={error ? true : undefined}
                aria-describedby={error ? "login-error" : undefined}
                onChange={(event) => { setPassword(event.target.value); setError(""); }} />
              <button type="button" className="login-password-toggle"
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((visible) => !visible)}>
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
                  stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                  <circle cx="12" cy="12" r="3" />
                  {showPassword && <path d="m3 3 18 18" />}
                </svg>
              </button>
            </div>

            <div className="login-forgot-row">
              <Link className="login-text-button" to="/forgot-password">Quên mật khẩu?</Link>
            </div>

            {error && <p id="login-error" className="login-error" role="alert">{error}</p>}
            <button className="login-submit" disabled={submitting}>
              {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
            </button>
          </form>

          <div className="login-divider"><span>Chưa có tài khoản?</span></div>
          <Link className="login-register" to="/register">Đăng ký tài khoản học viên</Link>
          <p className="login-account-note">Tài khoản giảng viên và quản trị viên do quản trị viên cấp.</p>
          {location.state?.message && <p className="login-notice" role="status">{location.state.message}</p>}
          {AUTH_MOCK && <p className="login-notice">Tài khoản mô phỏng: đăng ký tài khoản mới để thử. Không dùng mật khẩu thật.</p>}
          {error && <p><Link to="/verify-email">Xác minh email / gửi lại mã</Link></p>}
        </div>
      </section>
    </main>
  );
}
