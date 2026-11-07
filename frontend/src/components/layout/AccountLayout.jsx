import { Link } from "react-router-dom";
import { AUTH_MOCK } from "../../api/auth.api";
import "../../pages/login.css";

export default function AccountLayout({ title, subtitle, children, variant = "", icon }) {
  return <main className="login-screen">
    <aside className="login-brand-panel">
      <Link className="login-brand" to="/login">
        <span aria-hidden="true">L</span>LearnCloud
      </Link>
      <div className="login-brand-copy">
        <h2>Học qua video,<br />ôn đúng chỗ cần ôn.</h2>
        <p>Mỗi bài giảng có transcript, tóm tắt, flashcard và checkpoint — tất cả trong một nơi.</p>
      </div>
    </aside>
    <section className="login-form-panel"><div className={"login-form-content account-form " + variant}>
      {icon && <div className={"account-icon account-icon-" + icon} aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.2">
          {icon === "success" ? <><circle cx="16" cy="16" r="12" /><path d="m10 16 4 4 8-9" /></>
            : <><rect x="4" y="7" width="24" height="19" rx="2" /><path d="m5 9 11 8L27 9" /></>}
        </svg>
      </div>}
      <h1>{title}</h1><p className="login-subtitle">{subtitle}</p>
      {children}
      {AUTH_MOCK && <p className="login-notice">Chế độ mô phỏng: không gửi email thật. Mã thử: <strong>123456</strong>. Không dùng mật khẩu thật.</p>}
    </div></section>
  </main>;
}