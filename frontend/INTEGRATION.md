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

## 5. Enrollment and roadmap (frontend)
- POST /courses/{id}/enroll exists. A 409 is treated as already enrolled and triggers reload; the frontend also blocks repeated clicks.
- Pending backend: GET /students/me/courses returns an array of `{course:{id,title,...}, status:NOT_STARTED|IN_PROGRESS|COMPLETED, progress_percent, resume_lesson_id, unlocked_section_ids:[]}`. Missing endpoint shows a retryable error, never fake success or local fallback.
- `unlocked_section_ids` and completion in real mode must come from backend. Mock opens the first section, then requires checkpoint passes in order; watched-video completion alone never unlocks the next section.
- Mock enrollment, passes and progress persist per user in localStorage. New users must enroll; existing progress is preserved. Refresh/sign in again with the same account restores it.
- Discovery shows only published course metadata. Backend must enforce authorization and avoid returning protected content in metadata; UI filtering is not an access-control boundary.

## 6. Published lesson media (pending backend contract)
- GET /lessons/{id}/content: `{id,course_id,section_id,title,publication_status:"PUBLISHED",processing_status:"READY",summary:string,key_concepts:string[],transcript:[{start:number,text:string}]}`. `PROCESSING`/missing READY blocks rendering; FAILED shows an error; missing PUBLISHED blocks drafts. This is a proposed integration endpoint, not an existing backend feature.
- GET /lessons/{id}/video-url: `{video_url:string,expires_at:ISO8601|null}`. Authorize enrollment and section access every time. Backend returns signed URLs only for published content; do not expose raw storage keys in discovery metadata. Current backend does not provide this endpoint.
- Frontend refreshes 10 seconds before expiry and once automatically on a media error, then offers manual retry. Position and locally watched intervals survive URL refresh; a changed lesson resets them. Transcript seeks are clamped to media duration.
- Mock media is explicitly labeled demo and requires enrollment/section access too. l3?l5 use a sample video to exercise the complete roadmap, not authentic course content.
