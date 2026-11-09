const SESSION_KEY = "learncloud.auth.session";

export function readSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY));
    if (
      !session || typeof session.token !== "string" ||
      !Number.isFinite(session.expiresAt) || session.expiresAt <= Date.now()
    ) return null;
    return session;
  } catch {
    return null;
  }
}

export function writeSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

// Mock data is scoped to the authenticated account, not shared across users.
export function mockStorageKey(base) {
  const userId = readSession()?.user?.id;
  return `${base}:user:${userId ?? "anonymous"}`;
}
