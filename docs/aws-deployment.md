# AWS deployment and operations

## Verified state

This repository contains Lambda/Mangum packaging code, deployment examples, IAM templates, API Gateway, S3, EventBridge and Step Functions configuration. These artifacts establish intended integrations only. This documentation update made no AWS calls; current account resources, frontend URL, API routes, Lambda version/alias, Cognito configuration, RDS schema and pipeline state are **not verified**. Older runbooks include dated deployment/test observations; re-check them against a current inventory before acting.

## Deployment gates

1. Identify the target account, region, environment and approved operator. Confirm AWS identity using the team's approved access method; do not paste credentials or tokens into the repository.
2. Record the exact commit/SHA and review the working tree. Build backend/frontend artifacts from that commit; exclude `.env`, `.aws`, local caches and test-only handlers from production packages.
   Repository scripts are preparation helpers, not a complete deploy pipeline: `package_lambda.py` creates a code ZIP, `infrastructure/deployment/render-k4-k5-production.ps1` renders pipeline configuration, and `infrastructure/lambda/build.ps1` builds the RDS probe package. Verify dependency packaging and handler/runtime compatibility for the target function; do not assume the generic ZIP alone is a deployable production artifact.
3. Compare the intended source with the live API Gateway authorizer/routes, Lambda runtime/handler/configuration, Cognito user pool/client, RDS endpoint/schema and S3 bucket policies. Source templates are not live inventory.
4. Review least-privilege IAM, VPC connectivity, TLS/database configuration, CORS origins, S3 public-access block, encryption and logging. Keep `VIDEO_PIPELINE_ENABLED`, `VIDEO_AI_ENABLED` and `AI_WORKER_ENABLED` disabled until their non-production gates pass.
5. For schema changes, use a separately reviewed migration plan: verify database identity and migration registry, take an approved snapshot/backup, run the relevant read-only preflight, apply only the reviewed migration, then run postflight and integration checks. The migration history has conflicting `0004` files.
6. Deploy backend and frontend artifacts to their approved targets, update only reviewed API/Cognito/frontend settings, then check health, auth, logs and the affected business flow. Record artifact hashes and resulting version/alias, without recording secrets.
7. Enable asynchronous video/AI paths only after a non-production E2E run verifies duplicate/retry behavior, output state, logging and costs. The source defaults these features off.

## Rollback and recovery

- Keep the previous known-good backend version/alias and frontend artifact available through the team's deployment process. On application regression, route traffic back to that version/artifact and verify health/auth before resuming.
- Database changes need a migration-specific recovery decision. Prefer a reviewed forward-fix or restore plan based on the pre-change snapshot; do not drop tables, replay an ambiguous migration, or assume a down script is safe.
- For video pipeline retries, reconcile the upload/ledger, MediaConvert job and object state before submitting another job. Follow the specialized [video pipeline runbook](aws/video-pipeline-console-setup.md) and E2E [test runbook](operations/k4-k5-e2e-test-runbook.md); avoid blind redrive across a non-idempotent boundary.
- Preserve logs and request/execution identifiers. Never put access tokens, database URLs/passwords, raw AWS exceptions, transcript contents or presigned URLs in logs or tickets.

The repository does not provide a single script that deploys the complete frontend/backend/database/pipeline stack and rolls it back atomically. Follow the approved account-specific change process and retain the prior artifact/version for each independently deployed component.

## Security notes

- Prefer individual federated identities, MFA and narrowly scoped roles; do not share root access keys.
- Keep RDS private and restrict inbound access to the necessary security groups. Use private S3 buckets and least-privilege object prefixes.
- Keep database secrets in the approved secret-injection mechanism. The current backend reads `DATABASE_URL`; it does not fetch Secrets Manager values itself.
- Treat presigned URLs and auth tokens as temporary bearer credentials. Avoid screenshots, commits or chat messages containing them.
- Configure CloudWatch retention/alarms and budget alerts before running costly MediaConvert, Transcribe or Bedrock workloads.

## Related runbooks

- [API Gateway and Lambda notes](aws/api-gateway-lambda.md)
- [Cognito/RDS identity reconciliation](aws/cognito-rds-reconciliation.md)
- [S3 video playback notes](aws/s3-video-playback.md)
- [K4/K5 rollout preparation](aws/k4-k5-production-rollout.md)
- [Lambda package helper](../package_lambda.py)
- [K4/K5 configuration renderer](../infrastructure/deployment/render-k4-k5-production.ps1)

These documents contain implementation-specific steps and historical status. Confirm current resource names, permissions and schema before use; no production deployment is confirmed here.
