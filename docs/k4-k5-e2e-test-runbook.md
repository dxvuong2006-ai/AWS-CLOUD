# LearnCloud isolated K4 + K5 AWS E2E runbook

> Lesson 3 is retained as failed-run evidence. The follow-up Lesson 4 fixture,
> S3 copy order, rendered IAM policies, and reusable Lesson N workflow are in
> `database/k5/e2e4/README.md`.

This runbook creates test-only resources. It does not modify or reuse the production
K4 Lambda or production Step Functions state machine. Production must keep
`VIDEO_AI_ENABLED=false`.

## Fixed fixture identity

- Database: `learncloud_k5_test`; login/owner: `learncloud_k5_test_user`
- Lesson: `3`; upload: `00000000000000000000000000000003`; attempt: `0`
- Expected run ID: `158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409`
- Raw key: `lessons/3/raw/00000000000000000000000000000003.mp4`
- Expected processed key:
  `lessons/3/processed/00000000000000000000000000000003/attempt-1/video_720p.mp4`
- Expected transcript key:
  `ai-transcripts/158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409/transcript.json`

The run ID is SHA-256 of `00000000000000000000000000000003:0`.
The Step Functions execution ARN is deliberately not pre-seeded: K4 claim stores the
real `$$.Execution.Id`, and all K4/K5 callbacks must match it.

## Required test-only AWS resources

1. Lambda roles `learncloud-video-pipeline-k5-e2e-test-role` and
   `learncloud-ai-worker-k5-e2e-test-role`, using `lambda-trust.json`, the matching
   test policy in `infrastructure/iam/`, and the existing VPC ENI policy.
2. MediaConvert role `learncloud-mediaconvert-k5-e2e-test-role`, using
   `mediaconvert-trust.json` and `mediaconvert-k5-e2e-test-permissions.json`.
3. Step Functions role `learncloud-k4-k5-e2e-test-sfn-role`, using
   `step-functions-trust.json` and
   `k4-k5-e2e-test-step-functions-permissions.json`.
4. Pre-created log groups for both test Lambdas and a dedicated encrypted Step
   Functions log group with short test retention.
5. Lambda functions `learncloud-video-pipeline-k5-e2e-test` and
   `learncloud-ai-worker-k5-e2e-test`, using the test handlers/config examples.
6. A **Standard** state machine named `learncloud-k4-k5-e2e-test`, created from
   `k4-k5-e2e-test.asl.json` after replacing both test ARN placeholders.
7. A test-only EventBridge recovery rule rendered from
   `k4-k5-e2e-test-execution-failure.pattern.json`, scoped to the exact test state
   machine ARN and targeting the K4 test Lambda. Grant `events.amazonaws.com`
   invoke permission with this exact rule ARN as `SourceArn`.

Use a dedicated Lambda security group. RDS may accept TCP/5432 from that SG, but the
database credential must have grants only in `learncloud_k5_test`. Both test handlers
also fail closed unless `APP_ENV=k5-integration-test`, the driver is PostgreSQL, and
the URL user/database are exactly `learncloud_k5_test_user` / `learncloud_k5_test`.

## Build locally

Build the K4 test ZIP from the reviewed Linux Python 3.12 x86_64 dependency folder:

```powershell
.\.venv\Scripts\python.exe backend\scripts\build_video_pipeline_package.py `
  --dependencies build\video-dependencies-k4-fixed `
  --output build\video-pipeline-k4-k5-e2e-test.zip
```

Build the K5 test ZIP with the same reviewed dependency folder:

```powershell
.\.venv\Scripts\python.exe backend\scripts\build_ai_worker_package.py `
  --dependencies build\video-dependencies-k4-fixed `
  --output build\ai-worker-k4-k5-e2e-test.zip
```

Do not upload a ZIP until its reported SHA-256 and root handlers have been reviewed.

Render the three operator inputs locally; this script validates that both ARNs name
only the dedicated test Lambdas and makes no AWS call:

```powershell
.\infrastructure\deployment\render-k4-k5-e2e-test.ps1 `
  -PipelineLambdaArn '<test K4 Lambda ARN>' `
  -AiWorkerLambdaArn '<test K5 Lambda ARN>' `
  -VideoPath '<local MP4 path>' `
  -OutputDirectory 'build\k4-k5-e2e-before-upload'
```

Run the rendered SQL before the S3 upload. After upload, call the same script with
`-S3ETag '<ETag without quotes>'` and a different output directory. Use its rendered
input (and ASL if not created yet), but **do not rerun its duplicate SQL fixture**.

## Ordered AWS test procedure

1. Create the test roles, log groups, VPC/SG attachment, then the two test Lambdas.
   Inject the approved URL for **only** `learncloud_k5_test`; never copy the
   production `DATABASE_URL`. Keep the production functions unchanged.
2. Replace `${TEST_PIPELINE_LAMBDA_ARN}` and `${TEST_AI_WORKER_ARN}` in a local copy
   of the test ASL. Confirm neither rendered ARN names a production function. Create
   the separate Standard state machine with the test Step Functions role.
   Then create the exact-ARN test recovery rule and target the K4 test Lambda; its
   guarded wrapper routes only Step Functions status-change events to recovery.
3. Obtain the exact byte size of the local MP4. Replace `__VIDEO_SIZE_BYTES__` in a
   local copy of `add_k4_k5_e2e_fixture.sql` with that positive integer. In pgAdmin,
   connect as `learncloud_k5_test_user` and run the rendered SQL once.
4. Within 24 hours, upload the MP4 with `Content-Type: video/mp4` to the exact raw key.
   Record the object's current ETag without surrounding quotes. Do not overwrite it
   after recording the ETag.
5. Replace `__S3_ETAG_WITHOUT_QUOTES__` in the state-machine input template. Start
   exactly one execution of the **test** state machine.
6. Observe only the test execution/log groups. Expected state progression is:
   `CLAIMED -> SUBMITTING -> TRANSCODING -> VIDEO_READY -> COMPLETE`; Lesson is
   `PROCESSING -> TRANSCRIBING -> AI_PROCESSING -> REVIEW_REQUIRED`.
7. Success requires the final state `ReviewRequired`, run state `COMPLETE`, Lesson 3
   `REVIEW_REQUIRED`, non-empty transcript/summary/key concepts, one unapproved quiz,
   three questions, and at least one unapproved flashcard. No state publishes content.

## Retry and failure rules

- Claim and deterministic Transcribe start are idempotent for the same execution.
- Poll, verify, generate, and finalize are safe to retry; generate/finalize re-check
  persisted proof. Submit has no ASL retry because a CreateJob timeout is ambiguous.
- Do not use Step Functions Console Redrive after submit. If submission was uncertain,
  reconcile the MediaConvert job first. A failed execution records `FAILED`; use the
  application retry path to create a new attempt/run instead of reusing this run ID.
- Standard execution failure events are best effort. For this manual test, inspect the
  ledger directly after any stopped/timed-out execution before cleanup.

## Rollback / teardown

1. Stop only the test execution if still running. Confirm no test MediaConvert or
   Transcribe job remains active.
2. Disable/delete the test recovery rule and its Lambda permission, delete the test
   state machine, then delete the two test Lambdas and their dedicated log
   groups/roles. Remove the temporary RDS SG ingress rule if created.
3. Delete only the three test prefixes for Lesson 3: raw, processed, and the exact
   transcript run prefix shown above.
4. In pgAdmin, run `rollback_k4_k5_e2e_fixture.sql` only after all test execution is
   stopped. It has database/user/identity guards and deletes only fixture 3.
5. Do not reset PostgreSQL sequences. A later E2E test must allocate a new Lesson,
   upload ID, run ID, and S3 prefix.
