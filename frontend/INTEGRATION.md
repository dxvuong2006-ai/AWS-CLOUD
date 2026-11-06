# Frontend delivery: items 4–7

## Item 4: accounts
Default login remains the real backend. To exercise all account screens before backend delivery,
set VITE_USE_AUTH_MOCK=true and VITE_USE_MOCK=true in frontend/.env.local, then restart Vite.
Register a new mock student; code 123456 is valid for 10 minutes, at most 5 guesses.
Resend cooldown is 60 seconds, max 5 codes/hour/email/purpose. These are demo rules, not security.
Mock password hashes/data are local to the browser. Do not use real passwords. No email is sent.
Do not send mock tokens to a real backend.

Pending backend contracts (no backend code changed):
- POST /auth/register {name,email,password} -> {verification_required:true,message,retry_after}; public role must be STUDENT.
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
- Mock media is explicitly labeled demo and requires enrollment/section access too. l3-l5 use a sample video to exercise the complete roadmap, not authentic course content.

## 7. Watched ranges: frontend integration, backend work still pending
- One mock setting: `VITE_MOCK_COMPLETION_PERCENT` (1?100), default **10** to preserve the existing quick-test setup. Use **95** for the desired normal threshold. Restart Vite after changing env. Real mode never uses this value.
- Proposed POST /lessons/{id}/viewing-sessions returns `{id}`. Frontend starts on actual playback, serializes saves and sends PUT /lessons/{id}/progress with `{last_position_seconds,watched_ranges:[[start,end]],playback_session_id,sequence,request_id}`. Both endpoints still need backend implementation/review; no backend files were changed.
- No client `completed`, percent or authoritative duration is sent. After save, GET /courses/{id}/progress must return `{course_id,completion_threshold_percent,overall_percent,lessons:[{lesson_id,last_position_seconds,watched_ranges,watched_seconds,progress_percent,completed}]}`. Checkpoint permission is re-fetched from its API. Backend remains responsible for bounds, true duration, session timing, deduplication, enrollment, anomaly handling and checkpoint-based section access.
- Periodic save every 5s; also pause/end/navigation/hidden-page best-effort flush. A browser crash/forced close may lose the last unsent seconds. Cumulative intervals and serialized requests allow retries without double counting or older resume positions overwriting newer ones. Failed saves show retry; no fake completion.
- Mock merges overlapping intervals, stores resume separately and scopes data by user. Seeking clears the interval baseline; pausing does not add time; 2x counts content played, not wall-clock time. This is not proof of attention or a tamper-proof anti-cheating mechanism.

## Manual acceptance checks
1. In `.env.local` explicitly set `VITE_USE_MOCK=true`, `VITE_USE_AUTH_MOCK=true`; restart Vite. Create a throwaway student (8+ character password), verify with demo code 123456; then login. Real auth remains the default if auth mock is absent/false.
2. Register a course, check My Courses; refresh and sign in again with the same account. Second section remains locked until the first checkpoint is passed. A different account has separate enrollments/progress.
3. Play 10 seconds then pause; inspect localStorage progress ranges. Seek to end without playing: no full-video credit. Replay same segment: no duplicate. Pause 20s: no increase. 2x counts content. Reach configured threshold, checkpoint becomes available without flickering. Refresh page to restore position.
4. Use transcript to seek. At checkpoint, answer correctly then return to roadmap to see next section unlocked. Completing a video alone never unlocks it.
5. Simulate offline/network failures and expired media URLs: errors/retry preserve the current lesson and do not claim completion. Real end-to-end acceptance needs the pending backend endpoints above.

### Reset only the current demo account's progress in DevTools Console
Pause the video first. This keeps account and enrollment data:
```js
const userId = JSON.parse(sessionStorage.getItem('learncloud.auth.session') || '{}').user?.id;
if (userId) {
  for (const base of ['learncloud.mock.progress.v2', 'learncloud.mock.attempts', 'learncloud.mock.checkpoint-passes.v1']) {
    localStorage.removeItem(`${base}:user:${userId}`);
  }
  location.reload();
}
```
Real progress is not in localStorage; clearing it requires a backend test/reset facility. Do not clear all browser storage to reset one student's progress.

## Automated validation
- `npm test`: account lifecycle, OTP expiry/attempt limits, enrollment isolation/section gates, media publication and expiry, range merging/seek/2x, serialized saves, real payload shape, existing auth/quiz regression checks.
- `npm run test:browser`: Chrome/Edge headless, dedicated temporary profile and random local Vite port. Explicit mock env is scoped to the child process; it does not change `.env.local` or touch your normal browser profile. Exercises registration through checkpoint and account recovery. Real backend acceptance remains pending.
