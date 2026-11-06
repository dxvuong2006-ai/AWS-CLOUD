# Frontend delivery: items 4–7

## Item 4: accounts
Default login remains the real backend. To exercise all account screens before backend delivery,
set VITE_USE_AUTH_MOCK=true and VITE_USE_MOCK=true in frontend/.env.local, then restart Vite.
Register a new mock student; code 123456 is valid for 10 minutes, at most 5 guesses.
Resend cooldown is 60 seconds, max 5 codes/hour/email/purpose. These are demo rules, not security.
Mock password hashes/data are local to the browser. Do not use real passwords. No email is sent.
Do not send mock tokens to a real backend.

Pending backend contracts (no backend code changed):
- POST /auth/register {name,email,password} -> {message,retry_after}; public role must be STUDENT.
- POST /auth/verify-email {email,code}
- POST /auth/resend-verification and /auth/forgot-password {email} -> generic {message,retry_after}.
- POST /auth/reset-password {email,code,password}
- PATCH /auth/me {name} -> user; POST /auth/change-password {current_password,new_password}.
- Invalid/expired OTP: 400; duplicate email: 409; cooldown: 429; field errors: 422.
- Password changes/reset must invalidate old tokens on server. Profile email is read-only.
Current backend register may create users without verification; do not claim the real verification flow
works until those endpoints are delivered. Real API errors never silently fall back to mock.
