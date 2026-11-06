import { Link } from "react-router-dom";
import { AUTH_MOCK } from "../../api/auth.api";
import "../../pages/login.css";

export default function AccountLayout({ title, subtitle, children }) {
  return <main className="login-screen">
    <aside className="login-brand-panel">
      <Link className="login-brand" to="/login" style={{ textDecoration: "none" }}>
        <span aria-hidden="true">L</span>LearnCloud
      </Link>
      <div className="login-brand-copy">
        <h2>Học qua video,<br />ôn đúng chỗ cần ôn.</h2>
        <p>Mỗi bài giảng có transcript, tóm tắt, flashcard và checkpoint — tất cả trong một nơi.</p>
      </div>
    </aside>
    <section className="login-form-panel"><div className="login-form-content account-form">
      <h1>{title}</h1><p className="login-subtitle">{subtitle}</p>
      {AUTH_MOCK && <p className="login-notice">Chế độ mô phỏng: không gửi email thật. Mã thử: <strong>123456</strong>. Không dùng mật khẩu thật.</p>}
      {children}
    </div></section>
  </main>;
}
