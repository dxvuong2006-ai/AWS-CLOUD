# LearnCloud K5 isolated PostgreSQL database

This directory initializes only the local/test database `learncloud_k5_test`, owned
by `learncloud_k5_test_user`. The bootstrap has explicit database/user guards and
contains no `DROP` or `TRUNCATE` statement.

## Migration review

The repository cannot safely apply every migration by filename: four files claim
version `0004`, and the `0004_add_lesson_approved_status.sql`/legacy
`V2__allow_approved_lesson_status.sql` state is superseded by
`0004_remove_approved_lesson_status.sql`. The migration README is also stale because
`0003_reconcile_legacy_schema.sql` now exists.

For a new database, use the consolidated snapshot in
`initialize_learncloud_k5_test.sql`; do not replay the historical files afterward.
Its final state corresponds to this logical order:

1. `schema.sql` (`0001`, `0002` baseline; already includes legacy `V1`).
2. `0003_reconcile_legacy_schema.sql`.
3. `0004_remove_approved_lesson_status.sql` (canonical final Lesson status).
4. `0004_checkpoint_attempt_idempotency.sql` and
   `0004_cognito_auth_cutover.sql` (additive changes despite the duplicate version).
5. `0005_video_pipeline_ledger.sql`.
6. `V3__add_tutor_remediation_fields.sql`.
7. `0006_screen_workflows.sql`.
8. `0007_dual_auth.sql`.
9. `0008_local_auth_provisioning.sql`.

Do not apply `0004_add_lesson_approved_status.sql` or
`V2__allow_approved_lesson_status.sql` to a new database: `APPROVED` is absent from
the current `LessonStatus` model and was intentionally removed.

## Run in pgAdmin 4

1. Under **Login/Group Roles**, create `learncloud_k5_test_user`, enable **Can login**,
   and set a test-only password in pgAdmin's password field.
2. Under **Databases**, create `learncloud_k5_test` with owner
   `learncloud_k5_test_user`.
3. Register/connect to that database as `learncloud_k5_test_user`; do not use the
   production server registration.
4. Open Query Tool, load `initialize_learncloud_k5_test.sql`, verify the database and
   user shown in the toolbar, then execute the entire file once.
5. Open and execute `verify_learncloud_k5_test.sql`. It starts a read-only transaction
   and reports migrations, constraints, indexes, and the synthetic K5 fixture.

The seed is deliberately minimal: one synthetic instructor/course/section/lesson,
one video upload, and one `VIDEO_READY` pipeline run. It contains no password hash,
OTP, real account, transcript, quiz, or flashcard; K5 is expected to create the last
three kinds of learning content during E2E processing.
