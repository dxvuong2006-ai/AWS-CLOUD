// Historical flag name retained; true now means real FastAPI/PostgreSQL auth.
export const LOCAL_AUTH = import.meta.env.VITE_USE_AUTH_MOCK === "true";
export const AUTH_PROVIDER = LOCAL_AUTH ? "local" : "cognito";
