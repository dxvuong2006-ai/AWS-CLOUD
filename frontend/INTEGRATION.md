# Delivery: frontend items 4–7 and backend checkpoint item 8

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

## 8. Backend checkpoints (UI Flow v4, screens 17-27)
Status against the document: items 4-7 above are frontend delivery with mock coverage;
they do not imply completed real email, media, progress or AI services. The checkpoint
API/service files were empty before item 8. This item implements the checkpoint backend
and only the frontend submission/response wiring required by its contract.

Implemented routes (authenticated STUDENT only):
- GET `/sections/{section_id}/quiz?lesson_id={id}` returns the approved quiz for that
  section. Explicit public question DTOs omit both `correct_answer` and `explanation`.
  Returns `attempt_count`, `previous_score`; no question data is returned when access
  or mandatory remediation blocks the attempt.
- POST `/quizzes/{quiz_id}/attempts` requires `{request_id:UUID,lesson_id?:number,
  answers:[{question_id:number,selected_answer:string|null}]}`. Invalid question IDs,
  options, duplicate answers and client grading flags are rejected. Omitted/null
  answers are persisted as incorrect. Grade and all answers are committed atomically.
- GET `/quizzes/{quiz_id}/attempts?limit=20&offset=0` returns only the current student's
  persisted attempts, newest first. Results include `can_retry` and `remediation_required`.

Policy: published course, enrollment, approved quiz, all previous section checkpoints
passed, and server-stored completion of the specified published lesson are required.
Without lesson_id, at least one published lesson in the current section must be complete.
UI Flow v4 fixes passing at 80%; the checkpoint service does not accept a client threshold
or use an alternative quiz.passing_score. Scores 50-79% permit immediate retry. Below 50%,
all three server-verified remediation conditions are required: explanations completed,
lesson/flashcard review completed, and 2-3 practice questions with at least 2/3 correct.
Prior passes continue to unlock later sections even if a subsequent attempt fails.

Idempotency: retain the same UUID and payload until the outcome is known. PostgreSQL
locks the student's row to serialize submissions, plus a unique database index on
(student_id,quiz_id,request_id) guards retries. Same key/payload returns the saved attempt,
including after a low score blocks NEW attempts; changed payload with the same key gives
409. A deliberately new submission uses a new UUID. The UI shares in-flight submissions
and persists pending request data in user-scoped sessionStorage across reloads; it replays
a pending submission before trying to fetch a potentially locked quiz. Backend permission
controls the real-mode retry button. Existing demo quiz behavior is not the authority.

Deployment prerequisite: apply `database/migrations/0004_checkpoint_attempt_idempotency.sql`
after the existing baseline/migrations. It preserves old attempts, adds nullable UUID/hash
columns and creates `checkpoint_remediation`. This change does not run a migration against
your database. A fresh database also needs this migration after schema.sql.

Remaining integration dependencies:
- The progress backend from item 7 must populate authoritative LessonProgress.completed.
- Trusted AI/review/practice services must record the three verified remediation fields
  in checkpoint_remediation for the specific attempt. No student-facing endpoint accepts
  arbitrary "review completed" flags. Until those services exist, a below-50 attempt stays
  locked; this item does not pretend that the complete AI review flow is implemented.
- PostgreSQL concurrent-request acceptance should be run on an isolated test database
  after migration. The targeted unit/HTTP tests use in-memory SQLite and verify replay,
  constraints, transaction rollback, permissions and PostgreSQL lock SQL, not live PG races.

Targeted checks: backend `python -B -m unittest discover -s tests/unit -p test_checkpoint_backend.py -v`;
frontend `node --test tests/checkpoint-submit.test.cjs tests/mock-quiz.test.cjs` and the
`wire quiz` test in api-contract.test.cjs. No browser tests are required for item 8.

## 9. Checkpoint result UI and resumable drafts (frontend only)
Screens 17-22 now show start/previous score, answering, submit confirmation, and distinct
pass / optional review / mandatory AI-review outcomes. The server's `passed`, `can_retry`
and `remediation_required` remain authoritative in real mode; the frontend does not grade.
The result includes each returned answer's correct/incorrect status and unanswered items.
AI Tutor/practice navigation is still unavailable; its buttons remain explicitly disabled.

Draft policy:
- sessionStorage, same browser tab, scoped by authenticated user + quiz + fresh UUID session.
  Course and section IDs plus a signature of the public question/option data must also match.
- Clicking Start creates a session. Every selection and question navigation persists immediately.
  Refresh restores selections and question index. Closing the tab is not a durability guarantee;
  cross-device/cross-tab synchronization and server-side drafts are not implemented.
- Storage failures are visible and choices remain in memory. The UI does not claim an unsaved
  change is durable. A changed quiz cannot reuse the old draft; the learner starts a new session.
- Session UUID is also POST request_id. Pending payload is frozen on submission and retained
  on unknown network outcomes. Only confirmed success retires the draft; a submitted marker
  blocks late writes/restoration. A new attempt gets a new UUID and empty choices.
- Completion/cleanup happens in the API adapter even if the page was left while submitting.
  Request data remains retryable if local cleanup fails after the server accepted the attempt.

Results/history:
- History uses the EXISTING owner-scoped GET /quizzes/{id}/attempts?limit=20&offset=... .
  `/checkpoint-results/:quizId/:attemptId` reopens a result by searching those pages. Missing
  or unauthorized results show an error; no cached grade or another account's data is used.
- Mock history is persisted separately in localStorage under
  `learncloud.mock.checkpoint-history.v1:{quizId}:user:{userId}`. It stores immutable question
  review snapshots, demo explanations, UUID and score. The mock locks retries below 50%.
  To reset this demo history, remove the matching current-user keys as well as older progress/
  attempts/pass keys. Do not clear other accounts or all browser storage.

Backend gaps, documented only (NO backend files changed for item 9):
- Existing attempt responses contain question_id, selected_answer and is_correct, but not
  the historical question text, correct_answer or explanation. Return these as immutable
  post-submit snapshot fields in `answers[]` (question_text, position, correct_answer,
  explanation), for both submit responses and owner-scoped history. NEVER add solutions to
  the public pre-submit quiz response. The adapter/rendering already accepts those fields.
- Until these fields exist, real mode displays the status/selection it has and says that the
  explanation is unavailable; historical questions without text are identified by question ID.
  It does not invent an explanation or substitute today's edited question for historical text.
- A direct owner-scoped attempt-detail endpoint is an optional future optimization; current
  reopening works through paginated history. AI remediation confirmation remains item 8's gap.
- On a fresh tab/device, a blocked checkpoint does not currently disclose its quiz ID.
  Listing history from that section therefore needs safe quiz_id metadata or a section
  status endpoint from backend; existing result URLs remain usable with authentication.
  In the current tab the ID remembered when opening the quiz enables the history list.

Validation for item 9: targeted draft/result/submission/mock-quiz unit tests, the `wire quiz`
contract test, and frontend build. No browser runs and no full test-suite run. Lint is not
configured in this repository; no new lint tooling is introduced as part of this item.

## Item 10 - section access (frontend)
- Screens 11-13 use published course metadata and owner-scoped
  `GET /students/me/courses` -> `unlocked_section_ids`. Missing permission fails closed.
- Direct lesson navigation checks enrollment/unlock before mounting video/content hooks.
  The locked screen links to the previous section from the actual course order; navigation
  never treats watched percentage as permission to unlock the next section.
- Backend must return sections/lessons in learning order and authoritative unlock IDs after
  checkpoint passes (>=80%). It must independently enforce enrollment, publication and
  unlock on content, video URL, flashcard and checkpoint endpoints. UI guards are not security.
- Roadmap remount and the locked screen's retry button reload access. Existing opened pages
  may be stale after revocation; protected endpoints must reject requests regardless of UI.
- No backend changes. Backend progress/session integration and enrollment metadata remain
  prerequisites documented above; this item does not claim API bypass protection is complete.

## Item 11 - flashcards (frontend, screens 14-16)
- Entry points: sidebar `/flashcards` (enrolled course/section/lesson picker), roadmap lesson
  links and video. Deck route: `/courses/:courseId/sections/:sectionId/lessons/:lessonId/flashcards`.
- Proposed backend endpoint (NOT implemented here): `GET /lessons/{lesson_id}/flashcards`.
  Response: `{course_id, section_id, lesson_id, publication_status:"PUBLISHED", revision,
  cards:[{id,front,back,source_seconds?}]}`. Optional source time is displayed only when provided.
  Revision must change whenever published cards change. Empty cards
  is a supported state. Validate enrollment/publication/unlock and return only approved content;
  frontend rejects missing publication status, mismatched context and invalid cards.
- Real-mode API failures never fall back to mock. Mock uses lesson concepts/summary as clearly
  labeled demo cards, not AI-generated flashcards or a claim of production publication.
- Progress is intentionally browser-local localStorage, namespaced by authenticated user,
  course, section, lesson, deck revision and optional remediation session. Ratings and cursor
  persist immediately; back/front is transient. Refresh/logout/login on the same browser restores
  progress. No cross-device synchronization; if required, backend needs owner-scoped progress
  GET/PUT with deck revision and concurrency semantics. Storage errors are visible/retryable.
- Completion requires rating every card in the current round, not merely skipping to the end.
  Review-only rounds retain remembered cards and revisit weak cards; full review is also available.
- Future item 12 may supply `remediationSessionId` and URL-encoded `returnTo` query parameters.
  Return links accept only routes within the current course and preserve the session ID. The
  target remediation page and session ownership are item 12 responsibilities; no fake completion
  event is sent. Local card completion NEVER unlocks a section, checkpoint retry or remediation.
- No backend, browser or screenshot changes. Validate with flashcard/section unit tests and build.
