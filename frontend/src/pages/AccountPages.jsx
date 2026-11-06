import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AccountLayout from "../components/layout/AccountLayout";
import { registerStudent, verifyEmail, resendVerification, forgotPassword, resetPassword, updateProfile, changePassword } from "../api/auth.api";
import { accountError } from "../utils/accountErrors";
import { useAuth } from "../context/AuthContext";

function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const run = async (action) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { await action(); }
    catch (err) { if (alive.current) setError(accountError(err)); }
    finally { pending.current = false; if (alive.current) setBusy(false); }
  };
  return { busy, error, run };
}
function useCooldown(email, purpose) {
  const key = `learncloud.cooldown:${purpose}:${email.toLowerCase()}`;
  const [until, setUntil] = useState(() => Number(sessionStorage.getItem(key)) || 0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { setUntil(Number(sessionStorage.getItem(key)) || 0); }, [key]);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  return {
    seconds: Math.max(0, Math.ceil((until-now)/1000)),
    start: (seconds = 60) => {
      const value = Date.now() + seconds * 1000;
      sessionStorage.setItem(key, String(value)); setUntil(value); setNow(Date.now());
    },
  };
}
function Field({ label, id, ...props }) {
  return <div className="account-field"><label htmlFor={id}>{label}</label><input id={id} {...props} /></div>;
}
function ErrorText({ error }) { return error ? <p role="alert" className="login-error">{error}</p> : null; }
function checkPasswords(password, confirm) {
  if (password !== confirm) throw { status: 400, message: "Hai mật khẩu chưa khớp." };
}

export function RegisterPage() {
  const navigate = useNavigate();
  const { busy, error, run } = useAction();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });
  return <AccountLayout title="Đăng ký học viên" subtitle="Tạo tài khoản để bắt đầu học.">
    <form onSubmit={(e) => { e.preventDefault(); run(async () => {
      checkPasswords(form.password, form.confirm);
      const email = form.email.trim().toLowerCase();
      const result = await registerStudent({ ...form, email });
      if (result.verification_required !== true) {
        navigate("/login", { replace: true, state: { message: "Đã tạo tài khoản. Bạn có thể đăng nhập. Xác minh email chưa được kết nối trên hệ thống này." } });
        return;
      }
      sessionStorage.setItem(`learncloud.cooldown:verify:${email}`, String(Date.now()+(result.retry_after ?? 60)*1000));
      navigate("/verify-email?email=" + encodeURIComponent(email));
    }); }}>
      <Field id="register-name" label="Họ tên" required maxLength={100} autoComplete="name" {...field("name")} />
      <Field id="register-email" label="Email" type="email" required autoComplete="email" {...field("email")} />
      <Field id="register-password" label="Mật khẩu (8–128 ký tự)" type="password" required minLength={8} maxLength={128} autoComplete="new-password" {...field("password")} />
      <Field id="register-confirm" label="Nhập lại mật khẩu" type="password" required autoComplete="new-password" {...field("confirm")} />
      <ErrorText error={error} /><button className="login-submit" disabled={busy}>{busy ? "Đang tạo..." : "Tạo tài khoản"}</button>
    </form>
    <p><Link to="/verify-email">Đã đăng ký nhưng chưa xác minh?</Link></p>
    <p><Link to="/login">Đã có tài khoản? Đăng nhập</Link></p>
  </AccountLayout>;
}

export function VerifyEmailPage() {
  const [params] = useSearchParams(); const navigate = useNavigate();
  const [email, setEmail] = useState(params.get("email") || "");
  const [code, setCode] = useState(""); const [message, setMessage] = useState("");
  const { busy, error, run } = useAction(); const cooldown = useCooldown(email, "verify");
  return <AccountLayout title="Xác minh email" subtitle="Nhập mã 6 chữ số được gửi tới email của bạn.">
    <form onSubmit={(e) => { e.preventDefault(); run(async () => {
      await verifyEmail(email.trim(), code); navigate("/register-success", { replace: true });
    }); }}>
      <Field id="verify-email" label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field id="verify-code" label="Mã xác minh" required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />
      <ErrorText error={error} /><button className="login-submit" disabled={busy}>Xác minh</button>
    </form>
    <button className="login-register" disabled={busy || cooldown.seconds > 0 || !email.trim()} onClick={() => run(async () => {
      const result = await resendVerification(email.trim()); cooldown.start(result.retry_after ?? 60); setMessage(result.message);
    })}>{cooldown.seconds ? `Gửi lại sau ${cooldown.seconds}s` : "Gửi lại mã"}</button>
    {message && <p role="status">{message}</p>}
    <Link to="/register">← Quay lại đăng ký</Link>
  </AccountLayout>;
}

export function RegisterSuccessPage() {
  return <AccountLayout title="Đăng ký thành công" subtitle="Email của bạn đã được xác minh.">
    <Link className="login-submit" to="/login">Đăng nhập</Link>
  </AccountLayout>;
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState(""); const { busy, error, run } = useAction();
  const navigate = useNavigate();
  return <AccountLayout title="Quên mật khẩu" subtitle="Nhập email để nhận hướng dẫn đặt lại mật khẩu.">
    <form onSubmit={(e) => { e.preventDefault(); run(async () => {
      const normalized = email.trim().toLowerCase();
      const result = await forgotPassword(normalized);
      sessionStorage.setItem(`learncloud.cooldown:reset:${normalized}`, String(Date.now()+(result.retry_after ?? 60)*1000));
      navigate("/reset-password?email=" + encodeURIComponent(normalized));
    }); }}>
      <Field id="forgot-email" label="Email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <ErrorText error={error} /><button className="login-submit" disabled={busy}>Gửi mã đặt lại</button>
    </form><p><Link to="/login">← Quay lại đăng nhập</Link></p>
  </AccountLayout>;
}

export function ResetPasswordPage() {
  const [params] = useSearchParams(); const navigate = useNavigate();
  const [email, setEmail] = useState(params.get("email") || "");
  const [code, setCode] = useState(""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState("");
  const { busy, error, run } = useAction(); const cooldown = useCooldown(email, "reset");
  return <AccountLayout title="Đặt lại mật khẩu" subtitle="Nếu email phù hợp, mã hướng dẫn đã được gửi. Vui lòng kiểm tra hộp thư.">
    <form onSubmit={(e) => { e.preventDefault(); run(async () => {
      checkPasswords(password, confirm); await resetPassword(email.trim(), code, password);
      navigate("/login", { replace: true, state: { message: "Đã đặt lại mật khẩu. Vui lòng đăng nhập." } });
    }); }}>
      <Field id="reset-email" label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Field id="reset-code" label="Mã xác minh" required pattern="[0-9]{6}" maxLength={6} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
      <Field id="reset-password" label="Mật khẩu mới" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <Field id="reset-confirm" label="Nhập lại mật khẩu" type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <ErrorText error={error} /><button className="login-submit" disabled={busy}>Đặt lại mật khẩu</button>
    </form>
    <button className="login-register" disabled={busy || cooldown.seconds > 0 || !email.trim()} onClick={() => run(async () => {
      const result = await forgotPassword(email.trim()); cooldown.start(result.retry_after ?? 60);
    })}>{cooldown.seconds ? `Gửi lại sau ${cooldown.seconds}s` : "Gửi lại mã"}</button>
    <Link to="/login">← Quay lại đăng nhập</Link>
  </AccountLayout>;
}

export function ProfilePage() {
  const { user, refreshUser, logout } = useAuth(); const navigate = useNavigate();
  const [name, setName] = useState(user.name);
  const [current, setCurrent] = useState(""); const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState(""); const { busy, error, run } = useAction();
  return <div className="page account-profile"><h1>Hồ sơ và mật khẩu</h1>
    <p>{user.email} · {user.role}</p>
    <form className="card" onSubmit={(e) => { e.preventDefault(); run(async () => {
      await updateProfile(name); await refreshUser(); setMessage("Đã lưu hồ sơ.");
    }); }}>
      <Field id="profile-name" label="Họ tên" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
      <button className="btn-primary" disabled={busy}>Lưu thay đổi</button>
    </form>
    <form className="card" onSubmit={(e) => { e.preventDefault(); run(async () => {
      checkPasswords(password, confirm); await changePassword(current, password); logout();
      navigate("/login", { replace: true, state: { message: "Đã đổi mật khẩu. Vui lòng đăng nhập lại." } });
    }); }}>
      <h2>Đổi mật khẩu</h2>
      <Field id="profile-current" label="Mật khẩu hiện tại" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
      <Field id="profile-password" label="Mật khẩu mới" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />
      <Field id="profile-confirm" label="Nhập lại mật khẩu mới" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <button className="btn-primary" disabled={busy}>Đổi mật khẩu</button>
    </form>
    <ErrorText error={error} />{message && <p role="status">{message}</p>}
    <button className="btn-secondary" onClick={() => { logout(); navigate("/login", { replace: true }); }}>Đăng xuất</button>
  </div>;
}
