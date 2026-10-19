import { useState } from "react";
import "./Navbar.css";

const NAV_ITEMS = {
  STUDENT: [
    { label: "Khóa học", href: "/courses" },
    { label: "Khóa học của tôi", href: "/my-courses" },
  ],
  TEACHER: [
    { label: "Tổng quan", href: "/instructor/dashboard" },
    { label: "Quản lý khóa học", href: "/instructor/courses" },
  ],
  ADMIN: [
    { label: "Tổng quan", href: "/admin/dashboard" },
    { label: "Quản lý người dùng", href: "/admin/users" },
  ],
};

export default function Navbar({
  user = null,
  role = "STUDENT",
  onLogin,
  onLogout,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const currentRole = String(user?.role || role).toUpperCase();
  const navItems = NAV_ITEMS[currentRole] || NAV_ITEMS.STUDENT;
  const displayName =
    user?.full_name || user?.name || user?.email || "Người dùng";

  return (
    <header className="navbar">
      <div className="navbar__container">
        <a className="navbar__brand" href="/">
          <img
            className="navbar__logo"
            src="D:\PROJECTS\LMS_Cloud\frontend\logo.png"
            alt="LearnCloud logo"
          />
          <span className="navbar__brand-name">
            Learn<span>Cloud</span>
          </span>
        </a>

        <button
          type="button"
          className="navbar__menu-toggle"
          aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav
          className={`navbar__nav ${menuOpen ? "navbar__nav--open" : ""}`}
          aria-label="Điều hướng chính"
        >
          {navItems.map((item) => (
            <a
              key={item.href}
              className="navbar__link"
              href={item.href}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="navbar__account">
          {user ? (
            <>
              <div className="navbar__user">
                <div className="navbar__avatar">
                  {displayName.charAt(0).toUpperCase()}
                </div>

                <div className="navbar__user-info">
                  <span className="navbar__user-name">{displayName}</span>
                  <span className="navbar__user-role">
                    {currentRole === "INSTRUCTOR"
                      ? "Giảng viên"
                      : currentRole === "ADMIN"
                        ? "Quản trị viên"
                        : "Học viên"}
                  </span>
                </div>
              </div>

              <button
                type="button"
                className="navbar__button navbar__button--secondary"
                onClick={onLogout}
                disabled={!onLogout}
              >
                Đăng xuất
              </button>
            </>
          ) : (
            <button
              type="button"
              className="navbar__button navbar__button--primary"
              onClick={onLogin}
            >
              Đăng nhập
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
