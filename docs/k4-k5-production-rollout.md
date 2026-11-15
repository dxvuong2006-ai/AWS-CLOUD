# K4 + K5 production rollout plan

Scope: account `697589240877`, Region `ap-southeast-1`, database `learncloud`.
This runbook is preparation only. It does not call AWS/RDS and it keeps both AI
feature flags disabled until the canary gate.

## Readiness decision

**Conditional GO for one controlled canary; not an unconditional production GO.**

The K4/K5 runtime path is covered by 84 focused tests plus 9 subtests, the web UI
suite has 64 passing tests, and the same K4/K5 contract passed the isolated AWS
Lesson 4 E2E. The remaining gates are operational: run the production DB preflight,
confirm the exact MediaConvert queue, verify the K5 VPC/DB connection without writing
business data, verify the APAC Bedrock profile destinations/SCPs, and either repair or
explicitly waive the stale full-offline API test harness.

## Audited production flow

1. `learncloud-video-upload` matches S3 Object Created only below
   `lessons/*/raw/*` and starts the Standard workflow
   `learncloud-video-pipeline`.
2. K4 `claim` validates upload/lesson identity and takes ledger ownership. The
   deterministic upload/run identity makes a duplicate EventBridge delivery a no-op or
   a safe conflict, not another MediaConvert submission.
3. K4 `submit` creates one MediaConvert job. The ASL deliberately does not retry this
   non-idempotent boundary automatically.
4. K4 polls, verifies the processed object, and records `VIDEO_READY`.
5. `ai_enabled=false` ends safely at video-ready. `ai_enabled=true` calls only
   `learncloud-ai-worker`: start/poll Transcribe, then generate Bedrock content.
6. K4 `finalize_ai` validates persisted K5 content and atomically changes the Lesson to
   `REVIEW_REQUIRED` and the run to `COMPLETE`.
7. Every handled failure goes through K4 `fail`, which records a safe error and retry
   classification before the workflow fails.

The rendered ASL contains exactly these two Lambda ARNs and no unresolved placeholder:

- `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-pipeline`
- `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-ai-worker`

## Production versus the passing E2E stack

| Concern | E2E | Production preparation |
|---|---|---|
| Database | `learncloud_k5_test`, hard guard | `learncloud`, normal runtime; no test guard |
| Lambda handlers | test wrappers | `video_pipeline_handler.handler`, `ai_worker_handler.handler` |
| Resource scope | Lesson 4 only | `lessons/*/raw/*`, `lessons/*/processed/*`, `ai-transcripts/*` |
| AI enablement | required for the test | K4 and K5 flags initially `false` |
| State machine | dedicated test resource | existing production state machine, updated in place/versioned |
| Event source | manual controlled input | existing S3 EventBridge rule; duplicate delivery is expected |
| Database outcome | `COMPLETE/REVIEW_REQUIRED` | same contract, with human review before publish |

Production ZIP builds exclude `app/test_database_guard.py`,
`video_pipeline_test_handler.py`, and `ai_worker_test_handler.py`. Test support is now
opt-in to the package builders with `--include-test-support` and must never be used for
the production artifacts.

## Database gate

Run `database/checks/production_k4_k5_preflight.sql` in pgAdmin first. It is
transactionally read-only and refuses any database other than `learncloud`. It checks:

- required K4/K5 tables and content columns;
- exact ledger migration `0005` and its six integrity constraints;
- Lesson states/constraint and legacy `APPROVED` rows;
- application-role privileges required by K4/K5;
- upload/run identity integrity.

The prior read-only audit found ledger `0005` present, but production still registered
historical `0004` allowing `APPROVED`, while current code/schema publish directly after
review. `database/migrations/0009_reconcile_k4_k5_production.sql` is the prepared
alignment migration. It:

- refuses a non-`learncloud` database or incompatible/missing ledger;
- locks only `lessons` for the short DDL window;
- changes existing `APPROVED` rows to `PUBLISHED`;
- replaces the Lesson status CHECK and records `0009`;
- does not replay `0005`, alter K5 content, or touch pipeline identities.

This migration passed PostgreSQL 16.15 Docker validation against a simulated production
drift with an existing `APPROVED` row. Review the affected-row count and take the normal
RDS snapshot before applying it. If automatic `APPROVED -> PUBLISHED` is not the desired
business decision, stop and resolve those rows through the review workflow before
running `0009`.

Migrations `0007`/`0008`, `V3`, and the checkpoint migration concern authentication,
tutor remediation, or an alternate historical branch; do not apply them merely to
enable K4/K5.

## AWS resources

Keep and update in place:

- K4 Lambda `learncloud-video-pipeline` and role
  `LearnCloudVideoPipelineLambdaRole`;
- Standard state machine `learncloud-video-pipeline` and role
  `LearnCloudVideoStateMachineRole`;
- EventBridge rule `learncloud-video-upload` and its target role;
- production S3 bucket, existing MediaConvert queue, and
  `LearnCloudVideoMediaConvertRole`;
- RDS instance/database, VPC private subnets, and existing K4/RDS security path;
- existing Step Functions and K4 CloudWatch log groups.

Create:

- Lambda `learncloud-ai-worker` with a dedicated execution role and log group;
- a dedicated K5 security group, or an explicitly reviewed existing Lambda SG, with
  outbound access to RDS and AWS service endpoints/NAT;
- CloudWatch alarms/dashboard and a low monthly AWS Budget/cost-anomaly alert;
- optionally, a Step Functions published version and `PROD` alias for weighted rollout.

Update:

- K4 ZIP and environment, leaving `VIDEO_AI_ENABLED=false`;
- Step Functions role so it can invoke exactly K4 and K5;
- production ASL;
- K4/K5 inline policies and K5 VPC ENI permissions;
- EventBridge only if its currently deployed pattern/transformer differs from the
  rendered files. Do not create a second upload rule.

The exact production MediaConvert queue name is not recorded locally. Obtain it from
the current K4 configuration before rendering the final K4 policy. Also confirm the
private subnet IDs, K4/K5 security group IDs, production DB credential injection
mechanism, K5 role ARN, RDS KMS/bucket KMS requirements if any, and the actual APAC
inference-profile destination Regions/SCP permissions. Do not guess these values.

## IAM boundaries

- K4: log streams for its exact log group; S3 read/list on raw/processed Lesson
  prefixes; `mediaconvert:CreateJob` on the exact queue; `GetJob`; `iam:PassRole` only
  for `LearnCloudVideoMediaConvertRole` and only to MediaConvert.
- K5: log streams for its exact log group; S3 read on processed video/transcript and
  write only on `ai-transcripts/*`; Transcribe start restricted by Region, output
  bucket, and output-key pattern; get only `learncloud-k5-*` jobs; invoke only Nova
  Micro through the approved APAC inference profile.
- Both VPC Lambdas: the six ENI actions in
  `infrastructure/iam/lambda-vpc-permissions.json`. These EC2 APIs require
  `Resource: "*"`; do not broaden other statements.
- Step Functions: invoke exactly the two production Lambdas. Its CloudWatch Logs
  delivery APIs require `Resource: "*"`.
- EventBridge: `states:StartExecution` only on the exact production state-machine ARN.
- MediaConvert: read only raw video and write only processed output in the production
  bucket.

The source currently requires `DATABASE_URL`; it does not fetch SSM/Secrets Manager at
runtime. Reuse the existing approved production secret-injection process and the
least-privileged application DB user. Never place a credential in repository files,
the ZIP, ASL, policy JSON, or logs. Do not add Secrets Manager permission unless the
runtime is deliberately changed to retrieve it.

For `apac.amazon.nova-micro-v1:0`, allow the profile ARN in Singapore plus the Nova
foundation-model ARN in every destination Region, restricted by
`bedrock:InferenceProfileArn`. Before deployment, inspect the profile in the Console or
with `GetInferenceProfile` and confirm that Organizations SCPs permit every listed
destination; one blocked destination can fail cross-Region inference.

## Deployment order

1. Freeze/announce the short canary window. Record current Lambda code hashes,
   environment, role policies, ASL revision/version, EventBridge target/pattern, and
   alarm state. Take the normal recoverable RDS snapshot.
2. In pgAdmin, run the read-only preflight. Resolve every exception. Review legacy
   `APPROVED` count, then run `0009` only after business approval; rerun preflight.
3. Pre-create `/aws/lambda/learncloud-ai-worker` with retention and encryption matching
   policy. Create the dedicated K5 role/SG, attach K5 + VPC policies, and verify RDS SG
   ingress from K5 without broad CIDRs.
4. Create K5 Lambda from the production ZIP with the production handler, Python 3.12
   x86_64, private subnets, `APP_ENV=production`, and both AI flags `false`. Inject
   `DATABASE_URL` through the approved secret process. Do not invoke business actions.
5. Update K4 role/policy if required, then update K4 code/config. Keep
   `VIDEO_PIPELINE_ENABLED=true`, `VIDEO_AI_ENABLED=false`, and
   `AI_WORKER_ENABLED=false`.
6. Update the existing Step Functions role with the exact two Lambda ARNs. Publish the
   reviewed ASL as a version if available; preserve the old version/definition for
   rollback. Keep the upload rule unchanged and enabled only once.
7. Verify EventBridge: exactly one enabled S3 upload rule targets this workflow; no S3
   notification, API code path, or second rule also starts it; input transformer emits
   only `kind/bucket/key/etag`; target has retry limits and DLQ as appropriate.
8. Dry-check IAM with policy simulation/Console and verify Bedrock profile destinations,
   Transcribe output access, VPC egress/endpoints, quotas, log retention, alarms, and
   budget. No production Lesson should be used for this check.
9. Start a short maintenance window in which no other video upload/retry can be
   submitted. Enable K5 `AI_WORKER_ENABLED=true` first; it remains inert without a
   workflow call. Immediately before one controlled upload, set K4
   `VIDEO_AI_ENABLED=true`. Upload a single small English canary Lesson owned by a real
   test instructor in production.
10. Keep K4 `VIDEO_AI_ENABLED=true` until that execution reaches
    `COMPLETE/REVIEW_REQUIRED`: K4 deliberately checks the live flag again at
    `finalize_ai`, so turning it off after `claim` would fail the canary. Then set K4
    `VIDEO_AI_ENABLED=false`, end the maintenance window, and manually review all
    generated content and cost metrics. If uploads cannot be frozen, do not use this
    global-flag canary; first deploy a separate version/alias and explicitly isolated
    trigger path.
11. If every gate passes, re-enable K4 AI for a low-volume window. Expand gradually; a
    Step Functions alias can route a small percentage only if EventBridge targets the
    alias ARN. Otherwise use the one-upload flag window above.

## Duplicate and retry safety

EventBridge can invoke a rule/target more than once. Preserve the database ledger as the
authoritative idempotency layer and never rely on exactly-once delivery. Confirm there is
only one producer path. Keep `submit` without automatic retry because a timeout can occur
after MediaConvert accepted the job. Bounded polling and the K5 deterministic job name
are safe to retry. `RecordFailure -> Fail` is intentionally terminal; use explicit
recovery/reconcile rules rather than blindly redriving a failed execution across a
non-idempotent boundary.

## Monitoring and cost controls

Alarm on Step Functions `ExecutionsFailed/TimedOut/Throttled`, both Lambdas'
`Errors/Throttles/Duration`, MediaConvert failed jobs, Transcribe failed/long-running
jobs, and Bedrock invocation errors/throttles. Dashboard counts by safe workflow state
and watches runs stuck beyond their expected wait window. Never log transcript text,
prompt/output content, DB URLs, tokens, or raw AWS exception payloads.

Use a low initial reserved concurrency for K5, account/service quotas, a budget and cost
anomaly monitor. Track MediaConvert output minutes, Transcribe audio seconds, Bedrock
input/output tokens, Lambda duration, Step Functions transitions, and S3 growth. An
application inference profile may be added later for Bedrock usage attribution without
changing the content contract.

## Rollback

1. Set K4 `VIDEO_AI_ENABLED=false` first. New executions then remain K4 video-only.
2. Do not redrive failed executions until the last successful/non-idempotent boundary is
   known. Allow already-owned safe canaries to finish or stop them deliberately and
   reconcile the ledger.
3. Restore the prior state-machine version/definition and previous K4 ZIP/config if the
   failure is orchestration/K4 related. Disable K5 if the fault is isolated there.
4. Keep generated review data and migration `0009`; do not use destructive SQL rollback.
   Content in `REVIEW_REQUIRED` can be reviewed/rejected through the normal application.
5. Preserve logs, execution ARN, run ID, MediaConvert/Transcribe job IDs, and sanitized
   error code for the incident record.

## Offline test classification

- Focused K4/K5 suite: **PASS** — 84 tests, 9 subtests.
- Frontend suite: **PASS** — 64 tests.
- PostgreSQL 16.15 preflight/migration/postflight: **PASS**.
- Legacy full-offline unittest runner: **FAIL** — 161 tests, 51 failures, 21 errors.
  Twenty errors patch the removed `review_service.S3StorageAdapter` symbol; 35 assertions
  receive the newer authentication boundary's `401`; the remaining failures are mostly
  downstream logging/status assertions after that authentication short-circuit. One
  processing test shares the obsolete storage patch. These are test-harness/contract
  drift, not failures in the focused K4/K5 runtime suite, but the repository is still
  globally red. Repair or formally waive these named groups before broad rollout.

## Prepared artifacts

- `build/production-k4-k5-preparation/learncloud-video-pipeline-production.zip`
  SHA-256 `9eb0ac94f1dd12615ddac5ca6cbe82dfb76521a0effae1dbe85214c4052dd627`
- `build/production-k4-k5-preparation/learncloud-ai-worker-production.zip`
  SHA-256 `6c8d7f0bb39404a42a3ca96371c6135cba7286c94a8809a487598e95f6e2c80f`
- `build/production-k4-k5-preparation/video_pipeline.production.asl.json`
  SHA-256 `327301fff6a8091ff45340e214d855553a32d15f290c84b8caa0b5c064aba01f`
- `database/checks/production_k4_k5_preflight.sql`
  SHA-256 `cebc5f0201fb846be511514a7781aedae80d27aa39f50a5841de799d0d608d8d`
- `database/migrations/0009_reconcile_k4_k5_production.sql`
  SHA-256 `9cf986badbe80ab06825f5f431a9c779f40e746e18a32903abd12e0a55c6431e`

Regenerate the deployment bundle with
`infrastructure/deployment/render-k4-k5-production.ps1` after supplying the exact
MediaConvert queue name and role ARN. The current bundle intentionally omits the rendered
K4 inline policy because the queue name was not available and must not be guessed.
