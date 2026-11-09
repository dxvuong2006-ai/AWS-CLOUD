import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AUTH_MOCK, loginUser, fetchCurrentUser } from "../api/auth.api";
import { readSession, writeSession, clearSession } from "../api/session";
import { isAllowedRole } from "../utils/roles";
import {
  currentCognitoSession,
  refreshCognitoSession,
  signOutFromCognito,
} from "../api/cognito";

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
    signOutFromCognito().catch((error) => {
      console.error("Cognito sign-out failed.", error);
    });
  }, []);

  useEffect(() => {
    let active = true;
    const id = ++operation.current;
    const restoreSession = async () => {
      const session = AUTH_MOCK ? readSession() : await currentCognitoSession();
      if (!session) return null;
      writeSession({ ...session, user: readSession()?.user ?? null });
      const account = await fetchCurrentUser();
      return { session, account };
    };
    restoreSession()
      .then((account) => {
        if (!active || operation.current !== id) return;
        if (!account) {
          clearSession();
          return;
        }
        if (!isAllowedRole(account.account.role)) throw new Error("Unsupported role");
        writeSession({ ...account.session, user: account.account });
        setUser(account.account);
        setExpiresAt(account.session.expiresAt);
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
    const stored = readSession();
    if (stored?.token.startsWith("mock:")) {
      const timer = setTimeout(logout, Math.max(0, expiresAt - Date.now()));
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(async () => {
      try {
        const session = await refreshCognitoSession();
        if (!session) throw new Error("Cognito session could not be refreshed.");
        const account = await fetchCurrentUser();
        if (!isAllowedRole(account.role)) throw new Error("Unsupported role");
        writeSession({ ...session, user: account });
        setExpiresAt(session.expiresAt);
        setUser(account);
      } catch {
        logout();
      }
    }, Math.max(0, expiresAt - Date.now() - 60_000));
    return () => clearTimeout(timer);
  }, [expiresAt, logout]);

  const login = async (email, password) => {
    const id = ++operation.current;
    const response = await loginUser(email, password);
    if (operation.current !== id) return;
    if (!response.access_token || !Number.isFinite(response.expires_in) ||
        response.expires_in <= 0) {
      throw new Error("Phản hồi đăng nhập không hợp lệ.");
    }
    const expiry = Date.now() + response.expires_in * 1000;
    writeSession({ token: response.access_token, expiresAt: expiry, user: response.user ?? null });
    let account;
    try {
      account = response.user ?? await fetchCurrentUser();
    } catch (error) {
      if (!response.user) {
        clearSession();
        await signOutFromCognito();
      }
      throw error;
    }
    if (!isAllowedRole(account?.role)) {
      clearSession();
      await signOutFromCognito();
      throw new Error("Tài khoản không có vai trò được hỗ trợ.");
    }
    writeSession({ token: response.access_token, expiresAt: expiry, user: account });
    setExpiresAt(expiry);
    setUser(account);
  };

  const refreshUser = async () => {
    const account = await fetchCurrentUser();
    const session = readSession();
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
