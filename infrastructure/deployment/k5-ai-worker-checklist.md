# K5 AI Worker deployment checklist

This repository change is local-only. Do not enable either feature flag until a
non-production end-to-end run has completed.

1. Build Linux Python 3.12 x86_64 dependencies in a clean container and run
   `backend/scripts/build_ai_worker_package.py`. Verify ZIP root contains
   `ai_worker_handler.py`, `app/`, `ai_pipeline/`, `psycopg2/` and JSON schemas/prompts.
2. Create a dedicated execution role from `lambda-ai-worker-permissions.json`.
   Add the existing VPC ENI policy only when the function is attached to the RDS VPC.
3. Confirm private subnets can reach PostgreSQL, S3, Transcribe and Bedrock through
   approved NAT/VPC endpoints. Confirm the RDS security group accepts only the worker SG.
4. Create the separate `learncloud-ai-worker` function from the example config.
   Supply `DATABASE_URL` through the existing approved secret process; never commit it.
5. Keep `AI_WORKER_ENABLED=false` and `VIDEO_AI_ENABLED=false`. Import a rendered copy
   of the ASL only after replacing both Lambda ARN placeholders.
6. In non-production, enable only `AI_WORKER_ENABLED`, invoke each action with a test
   run, and verify logs contain IDs/codes but no transcript, URL or credential values.
7. Enable `VIDEO_AI_ENABLED` only for a controlled non-production K4→K5 execution.
   Verify one deterministic Transcribe job, one quiz, no duplicate flashcards, ledger
   `COMPLETE`, and Lesson `REVIEW_REQUIRED`.
8. Obtain approval and backups before any production change. There is no K5 roadmap
   migration in this MVP.
