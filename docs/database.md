# Database

## Source of truth

`database/schema.sql` is the fresh-install bootstrap snapshot. `database/migrations/` contains subsequent changes and historical/alternate migrations. It is not safe to infer a live database's version from these files: the database registry and actual objects must be inspected separately. The migration history has collisions around version `0004`; read [migration conventions and history](../database/migrations/README.md) before applying any SQL.

The database uses PostgreSQL and integer `SERIAL` primary keys in the bootstrap. SQLAlchemy models live in `backend/app/models/`. The current RDS schema and migration registry were not inspected in this documentation task.

## Bootstrap tables

| Table | Purpose and key relationships |
|---|---|
| `users` | Identity, unique email/Cognito subject, role and active status. |
| `courses` | Course owned by an instructor/admin user. |
| `sections` | Ordered sections belonging to a course. |
| `lessons` | Ordered lesson content and video-processing state under a section. |
| `enrollments` | Student-to-course membership; unique per pair. |
| `lesson_progress` | Per-student/per-lesson playback and completion state. |
| `viewing_sessions` | Playback session sequence tracking. |
| `progress_updates` | Idempotent progress request/response ledger. |
| `quizzes` | At most one quiz per section in the bootstrap schema. |
| `questions` | Quiz prompts, options and server-side correct answers. |
| `quiz_attempts` | Student submissions, score and pass state. |
| `quiz_answers` | Per-question answers belonging to an attempt. |
| `flashcards` | Ordered cards attached to lessons. |
| `tutor_sessions` | Student remediation session, optionally linked to an attempt. |
| `tutor_messages` | User/assistant messages in a Tutor session. |
| `schema_migrations` | Applied migration version registry. |

Migrations add or reconcile further structures, including upload/pipeline ledger tables, checkpoint idempotency/remediation state and account/progress fields. Review draft content is handled by the existing lesson/quiz content model rather than a dedicated `review_drafts` table. Do not treat migration-only tables or columns as present in every database until its registry/schema is verified.

## Relationships and safeguards

```text
users ──< courses ──< sections ──< lessons ──< flashcards
users >──< courses       via enrollments
users ──< lesson_progress / viewing_sessions / progress_updates
sections ── 0..1 quizzes ──< questions
users ──< quiz_attempts ──< quiz_answers >── questions
users ──< tutor_sessions ──< tutor_messages
```

Foreign keys and role-validation triggers protect important relationships. Unique constraints prevent duplicate enrollment, lesson/section position, quiz attempt number and answers per question/attempt. Quiz solutions are server-side data; public quiz responses must not expose them before submission. Backend checks remain necessary in addition to SQL constraints.

## Migration and test status

- Bootstrap SQL and migration scripts are present in source.
- PostgreSQL migration coverage exists in integration tests. The latest saved backend regression report records 69 PostgreSQL-gated cases as skipped, so those cases are not evidence of live PostgreSQL behavior.
- Migration application status on AWS/RDS is **not verified**. Do not run the migration runner against a shared/production database without a reviewed target, backup, preflight, apply plan and postflight.
- Specialized review/backup/apply/verify material is under [`database/`](database/) and the authoritative process is [the migration README](../database/migrations/README.md).

For the exact DDL, constraints and indexes, inspect [bootstrap schema](../database/schema.sql) and each migration. This summary intentionally avoids pretending the live database equals the repository snapshot.
