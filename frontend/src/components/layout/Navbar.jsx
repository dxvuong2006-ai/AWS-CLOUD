import { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import "./Navbar.css";
import logo from "../../public/logo.png";

const NAV_ITEMS = {
  STUDENT: [
    { label: "Khám phá", to: "/courses", icon: "compass" },
    { label: "Khóa học của tôi", to: "/my-courses", icon: "book-open" },
    { label: "Flashcard", to: "/flashcards", icon: "layers" },
    { label: "Tiến độ", to: "/progress", icon: "chart" },
  ],
  TEACHER: [
    { label: "Tổng quan", to: "/instructor/dashboard", icon: "home" },
    { label: "Khóa học", to: "/instructor/courses", icon: "book-open" },
    { label: "Học liệu AI", to: "/instructor/review-queue", icon: "sparkles" },
    {
      label: "Học viên & báo cáo",
      to: "/instructor/student-report",
      icon: "users",
    },
    { label: "Cài đặt", to: "/instructor/settings", icon: "settings" },
  ],
  ADMIN: [
    { label: "Tài khoản", to: "/admin/users", icon: "users" },
    { label: "Vai trò & quyền", to: "/admin/roles", icon: "shield" },
    { label: "Giám sát hệ thống", to: "/admin/monitoring", icon: "activity" },
  ],
};

const ROLE_LABELS = {
  STUDENT: "Học viên",
  TEACHER: "Giảng viên",
  INSTRUCTOR: "Giảng viên",
  ADMIN: "Quản trị viên",
};

const ROLE_HEADINGS = {
  STUDENT: "HỌC VIÊN",
  TEACHER: "GIẢNG VIÊN",
  INSTRUCTOR: "GIẢNG VIÊN",
  ADMIN: "QUẢN TRỊ VIÊN",
};

const ICONS = {
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m16.2 7.8-2.7 5.7-5.7 2.7 2.7-5.7 5.7-2.7Z" />
    </>
  ),
  "book-open": (
    <>
      <path d="M12 7v14" />
      <path d="M3 18V5a1 1 0 0 1 1-1h3a5 5 0 0 1 5 5 5 5 0 0 1 5-5h3a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-4a4 4 0 0 0-4 2 4 4 0 0 0-4-2H4a1 1 0 0 1-1-1Z" />
    </>
  ),
  layers: (
    <>
      <path d="m12 2 9 5-9 5-9-5 9-5Z" />
      <path d="m3 12 9 5 9-5M3 17l9 5 9-5" />
    </>
  ),
  chart: (
    <>
      <path d="M3 3v18h18" />
      <path d="m19 9-5 5-4-4-5 5" />
    </>
  ),
  home: (
    <>
      <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-6v-7h-4v7H4a1 1 0 0 1-1-1V10Z" />
    </>
  ),
  sparkles: (
    <>
      <path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" />
      <path d="m19 14 1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="10" cy="7" r="4" />
      <path d="M20 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 0 2Z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  activity: (
    <>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </>
  ),
};

function NavIcon({ name }) {
  return (
    <svg
      className="navbar__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  );
}

export default function Navbar({ user, role, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const rawRole = String(user?.role || role).toUpperCase();
  const currentRole = rawRole === "INSTRUCTOR" ? "TEACHER" : rawRole;
  const navItems = NAV_ITEMS[currentRole] || NAV_ITEMS.STUDENT;

  const displayName =
    user?.full_name || user?.name || user?.email || "Tài khoản demo";

  const roleLabel = ROLE_LABELS[rawRole] || "Học viên";
  const heading = ROLE_HEADINGS[rawRole] || "HỌC VIÊN";

  return (
    <aside className="navbar">
      <Link
        to="/"
        className="navbar__brand"
        aria-label="LearnCloud - Trang chủ"
      >
        <img className="navbar__logo" src={logo} alt="LearnCloud" />
        <span className="navbar__brand-name">LearnCloud</span>
      </Link>

      <div className="navbar__section-title">{heading}</div>

      <nav
        className={`navbar__nav ${menuOpen ? "navbar__nav--open" : ""}`}
        aria-label="Điều hướng chính"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            className={({ isActive }) =>
              `navbar__link ${isActive ? "navbar__link--active" : ""}`
            }
            onClick={() => setMenuOpen(false)}
          >
            <NavIcon name={item.icon} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="navbar__account">
        {accountMenuOpen && onLogout && (
          <div className="navbar__account-menu">
            <button
              type="button"
              className="navbar__logout"
              onClick={() => {
                setAccountMenuOpen(false);
                onLogout();
              }}
            >
              <span className="navbar__logout-icon">↪</span>
              Đăng xuất
            </button>
          </div>
        )}

        <button
          type="button"
          className="navbar__account-trigger"
          onClick={() => setAccountMenuOpen((open) => !open)}
          aria-expanded={accountMenuOpen}
          aria-label="Thông tin tài khoản"
        >
          <div className="navbar__avatar">
            {displayName.charAt(0).toUpperCase()}
          </div>

          <div className="navbar__user-info">
            <span className="navbar__user-name" title={displayName}>
              {displayName}
            </span>
            <span className="navbar__user-role">{roleLabel}</span>
          </div>

          <span className="navbar__account-chevron">
            {accountMenuOpen ? "⌄" : "⌃"}
          </span>
        </button>
      </div>
    </aside>
  );
}
