# LearnCloud architecture

## System view

```text
Browser ── React + Vite (frontend/) ── HTTPS/JSON ── FastAPI (backend/)
                                                        ├── PostgreSQL (database/)
                                                        ├── Storage adapter: local / S3
                                                        ├── Auth: Cognito JWT / opt-in local auth
                                                        ├── AI adapter: mock / Bedrock
                                                        └── Video/transcription adapters

AWS pipeline configuration (proposed/available in source):
S3 event → EventBridge → Step Functions → Lambda workers
                                  ├── MediaConvert
                                  ├── Transcribe
                                  └── Bedrock → PostgreSQL/S3
Frontend static build → S3/CloudFront (deployment target)
API Gateway → Lambda + Mangum → FastAPI → RDS PostgreSQL (deployment target)
```

## Components in this repository

| Component | Responsibility and evidence |
|---|---|
| `frontend/` | React/Vite pages, Amplify authentication, API client and browser tests. Frontend route visibility is not authorization. |
| `backend/app/api/` | FastAPI routers and request/response validation; these registered routers produce the OpenAPI contract. |
| `backend/app/services/` | Application rules for authentication, courses, upload/video, progress, quiz, review, Tutor and analytics. |
| `backend/app/repositories/`, `models/` | Persistence queries and SQLAlchemy entities. |
| `backend/app/adapters/` | Local/AWS implementations for storage, video processing, transcription and AI. |
| `ai_pipeline/` | Transcript normalization, summary, quiz, key-concept and Tutor-context processing, JSON schemas and tests. |
| `database/` | PostgreSQL bootstrap schema, ordered/historical migrations, checks and test fixtures. |
| `infrastructure/` | Lambda package examples, IAM policy templates, EventBridge patterns, ASL and deployment helpers. These are source artifacts, not proof of deployed resources. |

## Main data and request paths

1. The browser authenticates and sends a bearer access token to FastAPI. Backend dependencies validate identity and enforce active-account, role, ownership, enrollment and learning-access rules.
2. Instructors create course structure and lesson content. Video upload uses a presigned S3 URL; a separate confirmation route and processing state track the upload lifecycle.
3. When configured, S3/EventBridge/Step Functions orchestrate video and AI workers. Lesson content remains subject to instructor review/approval before publication.
4. Students enroll, read accessible published material, save lesson progress, submit quiz attempts, and use permitted review/Tutor flows. The backend/database own grades, completion and unlock decisions.

## Local and AWS modes

Local development runs Vite and Uvicorn, with PostgreSQL from the Compose file when a local database is needed. Local auth, local video queue, mock AI and SQLite paths are separate modes and must be explicitly configured where required.

The AWS architecture is represented by code/configuration for Cognito, API Gateway, Lambda, RDS, S3, CloudFront, IAM, EventBridge and Step Functions. Feature flags for the video/AI pipeline default off. No AWS inventory or runtime check was performed for this documentation update; deployed topology and feature availability are **not verified**. See [AWS deployment](aws-deployment.md).

## Security boundaries

- Browser bundles may contain public Cognito/API identifiers but never private keys, database credentials or AWS credentials.
- S3 remains private; presigned URLs are short-lived bearer capabilities and must not be logged/shared.
- API authorization belongs in backend dependencies/services and database constraints, not UI checks.
- Runtime database roles and AWS roles should follow the reviewed least-privilege configuration. Existing sample policies/configs need environment-specific review.
