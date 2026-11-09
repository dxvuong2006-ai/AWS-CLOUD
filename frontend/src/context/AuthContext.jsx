import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { loginUser, fetchCurrentUser } from "../api/auth.api";
import { readSession, writeSession, clearSession } from "../api/session";
import { isAllowedRole } from "../utils/roles";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expiresAt, setExpiresAt] = useState(null);
  const operation = useRef(0);

  const logout = useCallback(() => {
    operation.current += 1;
    clearSession();
    setUser(null);
    setExpiresAt(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    const session = readSession();
    const id = ++operation.current;
    if (!session) {
      clearSession();
      setLoading(false);
      return;
    }
    fetchCurrentUser()
      .then((account) => {
        if (!active || operation.current !== id) return;
        if (!isAllowedRole(account.role)) throw new Error("Unsupported role");
        writeSession({ ...session, user: account });
        setUser(account);
        setExpiresAt(session.expiresAt);
      })
      .catch(() => {
        if (active && operation.current === id) logout();
      })
      .finally(() => {
        if (active && operation.current === id) setLoading(false);
      });
    return () => { active = false; };
  }, [logout]);

  useEffect(() => {
    window.addEventListener("learncloud:unauthorized", logout);
    return () => window.removeEventListener("learncloud:unauthorized", logout);
  }, [logout]);

  useEffect(() => {
    if (!expiresAt) return;
    const timer = setTimeout(logout, Math.max(0, expiresAt - Date.now()));
    return () => clearTimeout(timer);
  }, [expiresAt, logout]);

  const login = async (email, password) => {
    const id = ++operation.current;
    const response = await loginUser(email, password);
    if (operation.current !== id) return;
    if (!isAllowedRole(response.user?.role) || !response.access_token ||
        !Number.isFinite(response.expires_in) || response.expires_in <= 0) {
      throw new Error("Phản hồi đăng nhập không hợp lệ.");
    }
    const expiry = Date.now() + response.expires_in * 1000;
    writeSession({ token: response.access_token, expiresAt: expiry, user: response.user });
    setExpiresAt(expiry);
    setUser(response.user);
  };

  const refreshUser = async () => {
    const session = readSession();
    const account = await fetchCurrentUser();
    if (!session || readSession()?.token !== session.token) return;
    writeSession({ ...session, user: account });
    setUser(account);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth requires AuthProvider");
  return context;
}
