# Lesson 4 isolated K4 + K5 E2E

## Fixed identity

- Database/user: `learncloud_k5_test` / `learncloud_k5_test_user`
- Lesson ID: `4`
- Upload ID: `00000000000000000000000000000004`
- Attempt: `0`
- Run ID: `65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6`
- Source copy key:
  `lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4`
- Lesson 4 raw key:
  `lessons/4/raw/00000000000000000000000000000004.mp4`
- Expected output key:
  `lessons/4/processed/00000000000000000000000000000004/attempt-1/video_720p.mp4`
- Expected transcript key:
  `ai-transcripts/65dcd70eecb600ef0ff1ec0dd3bc35c5b4444cea5668d9fd8594d689ce58eee6/transcript.json`

The run ID is SHA-256 of the UTF-8 string
`00000000000000000000000000000004:0`. The execution ARN is intentionally absent;
K4 claim persists the real `$$.Execution.Id`.

## Render local files

First read the existing Lesson 2 object's metadata. This is a read-only AWS command
that the operator runs; the render script itself makes no AWS call:

```powershell
$source = aws s3api head-object `
  --bucket learncloud-videos-mentorcloud `
  --key 'lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4' `
  --region ap-southeast-1 | ConvertFrom-Json

if ($source.ContentType -ne 'video/mp4' -or [long]$source.ContentLength -le 0) {
  throw 'Lesson 2 source object is not a non-empty video/mp4.'
}
```

Render SQL, ASL, the three least-privilege policies, and the identity manifest:

```powershell
.\infrastructure\deployment\render-k4-k5-e2e-test.ps1 `
  -PipelineLambdaArn 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-pipeline-k5-e2e-test' `
  -AiWorkerLambdaArn 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-ai-worker-k5-e2e-test' `
  -LessonId 4 `
  -VideoSizeBytes ([long]$source.ContentLength) `
  -OutputDirectory 'build\k4-k5-e2e-lesson4-before-copy'
```

## pgAdmin, S3, IAM, and execution order

1. Before any S3 copy, inspect the enabled EventBridge `Object Created` rules. If a
   production rule matches `lessons/4/raw/*.mp4`, stop: do not rely on the production
   claim ignoring this object. The copy must occur only when the destination is
   excluded from every production target and no test upload rule can auto-start a
   second execution. This runbook starts the test state machine manually once.

2. In pgAdmin, verify the selected database/user:

   ```sql
   SELECT current_database(), current_user;
   ```

   Both values must be `learncloud_k5_test` and `learncloud_k5_test_user`.

3. Open and run only
   `build\k4-k5-e2e-lesson4-before-copy\add-k4-k5-e2e-lesson-4-fixture.rendered.sql`.
   The transaction checks the database, owner, schema, Lesson 3 failure evidence,
   sequence position, and all Lesson 4 identities. It inserts no pipeline run and
   never updates Lesson 3.

4. After the SQL commits, copy the Lesson 2 video. Copying after the insert is
   required because K4 verifies that the object's `LastModified` is inside the
   upload intent's 24-hour validity window.

   ```powershell
   aws s3api copy-object `
     --bucket learncloud-videos-mentorcloud `
     --copy-source 'learncloud-videos-mentorcloud/lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4' `
     --key 'lessons/4/raw/00000000000000000000000000000004.mp4' `
     --metadata-directive REPLACE `
     --content-type video/mp4 `
     --region ap-southeast-1
   ```

5. Read the target metadata and fail closed on any mismatch:

   ```powershell
   $target = aws s3api head-object `
     --bucket learncloud-videos-mentorcloud `
     --key 'lessons/4/raw/00000000000000000000000000000004.mp4' `
     --region ap-southeast-1 | ConvertFrom-Json

   if ([long]$target.ContentLength -ne [long]$source.ContentLength -or
       $target.ContentType -ne 'video/mp4') {
     throw 'Lesson 4 copy metadata does not match the SQL fixture.'
   }
   $lesson4Etag = ([string]$target.ETag).Trim('"')
   ```

6. Render again into a new directory to bind the real target ETag:

   ```powershell
   .\infrastructure\deployment\render-k4-k5-e2e-test.ps1 `
     -PipelineLambdaArn 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-pipeline-k5-e2e-test' `
     -AiWorkerLambdaArn 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-ai-worker-k5-e2e-test' `
     -LessonId 4 `
     -VideoSizeBytes ([long]$target.ContentLength) `
     -S3ETag $lesson4Etag `
     -OutputDirectory 'build\k4-k5-e2e-lesson4-ready'
   ```

   Do not run the second rendered SQL; Lesson 4 already exists.

7. Replace the inline policies on only these test roles with the rendered files:

   - K4 Lambda role: `k4-e2e-test-lambda-permissions.rendered.json`
   - K5 Lambda role: `k5-e2e-test-lambda-permissions.rendered.json`
   - MediaConvert test role: `mediaconvert-k5-e2e-test-permissions.rendered.json`

   The K5 policy allows `s3:PutObject` only below the exact Lesson 4 run transcript
   prefix. `StartTranscriptionJob` uses `Resource: "*"` because that action has no
   resource type, but conditions bind the request to the exact region, bucket, and
   transcript key. `GetTranscriptionJob` remains bound to the exact job ARN.

8. Do not recreate the active state machine unless its Lambda ARNs changed. Start
   one execution with:

   `build\k4-k5-e2e-lesson4-ready\k4-k5-e2e-lesson-4-input.rendered.json`

Keep the Lesson 3 DB rows, S3 objects, execution history, and logs unchanged.

## Reuse for Lesson N

Use the same renderer with `-LessonId N`. Without `-UploadId`, it derives a
32-character lowercase hexadecimal upload ID from N, computes `SHA256(upload_id:0)`,
and renders SQL, input, IAM policies, ASL, and a manifest. The generic SQL requires
the Lesson sequence to be exactly `N - 1`; it fails rather than guessing or filling
gaps. Supply either `-VideoPath` for a local file or `-VideoSizeBytes` for an S3-side
copy, never both.
