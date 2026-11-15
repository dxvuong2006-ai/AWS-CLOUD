# K5 test 2: Python in 2 Minutes

Constants for this isolated fixture:

- Database/user: `learncloud_k5_test` / `learncloud_k5_test_user`
- Lesson ID: `2`
- Upload ID: `00000000000000000000000000000002`
- Attempt: `0`
- Run ID: `038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de`
- Execution ARN: `arn:aws:states:ap-southeast-1:000000000000:execution:k5-local:e2e-fixture-2`
- Video S3 key: `lessons/2/processed/00000000000000000000000000000002/attempt-0/video_720p.mp4`
- Expected transcript key with the default prefix:
  `ai-transcripts/038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de/transcript.json`

`run_id` is SHA-256 of the UTF-8 string
`00000000000000000000000000000002:0`.

## Operator order

1. In pgAdmin, connect to `learncloud_k5_test` as `learncloud_k5_test_user` and
   run `add_python_in_2_minutes_fixture.sql` once. Confirm the returned Lesson ID
   and keys.
2. Upload the English MP4 to bucket `learncloud-videos-mentorcloud` at the exact
   video key above.
3. Confirm the deployed worker already uses `TRANSCRIBE_LANGUAGE_CODE=en-US`.
   The Lambda event contract does not accept a language override.
4. Invoke `start_transcription.json` once.
5. Invoke `poll_transcription.json` until its status is `COMPLETED`.
6. Invoke `generate_content.json` once. Expected output is
   `{"completed":true,"run_id":"038ef54af3fd1e35aa1d23c47ea80791f82e601aad1caece9975147a194e47de"}`.

The SQL script contains only INSERT statements after read-only guards. It does
not update or delete fixture 1.
