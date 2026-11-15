[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PipelineLambdaArn,

    [Parameter(Mandatory = $true)]
    [string]$AiWorkerLambdaArn,

    [ValidateRange(1, 2147483647)]
    [int]$LessonId = 4,

    [ValidatePattern('^[a-f0-9]{32}$')]
    [string]$UploadId,

    [string]$VideoPath,

    [ValidateRange(1, 524288000)]
    [long]$VideoSizeBytes,

    [string]$S3ETag,

    [ValidatePattern('^\d{12}$')]
    [string]$AccountId = '697589240877',

    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$MediaConvertQueueName = 'learncloud-k5-e2e-test-queue',

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pipelinePattern = '^arn:aws:lambda:ap-southeast-1:\d{12}:function:learncloud-video-pipeline-k5-e2e-test$'
$workerPattern = '^arn:aws:lambda:ap-southeast-1:\d{12}:function:learncloud-ai-worker-k5-e2e-test$'

if ($PipelineLambdaArn -notmatch $pipelinePattern) {
    throw 'Pipeline ARN must name the dedicated ap-southeast-1 K5 E2E test Lambda.'
}
if ($AiWorkerLambdaArn -notmatch $workerPattern) {
    throw 'Worker ARN must name the dedicated ap-southeast-1 K5 E2E test Lambda.'
}
if ($PipelineLambdaArn.Split(':')[4] -ne $AccountId -or
    $AiWorkerLambdaArn.Split(':')[4] -ne $AccountId) {
    throw 'Both test Lambda ARNs must belong to AccountId.'
}
if ($PSBoundParameters.ContainsKey('S3ETag') -and
    $S3ETag -notmatch '^[A-Fa-f0-9]{32}(?:-\d+)?$') {
    throw 'S3 ETag must be supplied without quotes.'
}

$hasVideoPath = $PSBoundParameters.ContainsKey('VideoPath') -and
    -not [string]::IsNullOrWhiteSpace($VideoPath)
$hasVideoSize = $PSBoundParameters.ContainsKey('VideoSizeBytes')
if ($hasVideoPath -eq $hasVideoSize) {
    throw 'Supply exactly one of VideoPath or VideoSizeBytes.'
}
if ($hasVideoPath) {
    $video = Get-Item -LiteralPath $VideoPath
    if ($video.PSIsContainer -or $video.Length -le 0 -or $video.Length -gt 524288000) {
        throw 'Video must be a non-empty file no larger than 500 MiB.'
    }
    $resolvedVideoSize = [long]$video.Length
} else {
    $resolvedVideoSize = $VideoSizeBytes
}

if ([string]::IsNullOrWhiteSpace($UploadId)) {
    $UploadId = $LessonId.ToString('x32')
}
$previousLessonId = $LessonId - 1
$rawKey = "lessons/$LessonId/raw/$UploadId.mp4"
$outputKey = "lessons/$LessonId/processed/$UploadId/attempt-1/video_720p.mp4"

$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $identityBytes = [System.Text.Encoding]::UTF8.GetBytes("${UploadId}:0")
    $runId = -join ($sha256.ComputeHash($identityBytes) | ForEach-Object {
        $_.ToString('x2')
    })
} finally {
    $sha256.Dispose()
}
$transcriptKey = "ai-transcripts/$runId/transcript.json"

$output = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {
    throw "Output directory already exists: $output"
}
[void](New-Item -ItemType Directory -Path $output)

$aslTemplate = Join-Path $repoRoot 'infrastructure\step-functions\k4-k5-e2e-test.asl.json'
$inputTemplate = Join-Path $repoRoot 'infrastructure\step-functions\k4-k5-e2e-test-input.template.json'
$lesson4Sql = Join-Path $repoRoot 'database\k5\e2e4\add_k4_k5_e2e_fixture.sql'
$genericSql = Join-Path $repoRoot 'database\k5\e2e\add_k4_k5_e2e_fixture.template.sql'
$k4PolicyTemplate = Join-Path $repoRoot 'infrastructure\iam\templates\k4-e2e-test-lambda-permissions.template.json'
$k5PolicyTemplate = Join-Path $repoRoot 'infrastructure\iam\templates\k5-e2e-test-lambda-permissions.template.json'
$mediaConvertPolicyTemplate = Join-Path $repoRoot 'infrastructure\iam\templates\mediaconvert-k5-e2e-test-permissions.template.json'

$asl = (Get-Content -LiteralPath $aslTemplate -Raw).Replace(
    '${TEST_PIPELINE_LAMBDA_ARN}', $PipelineLambdaArn
).Replace('${TEST_AI_WORKER_ARN}', $AiWorkerLambdaArn)

if ($LessonId -eq 4 -and $UploadId -eq '00000000000000000000000000000004') {
    $fixtureSql = (Get-Content -LiteralPath $lesson4Sql -Raw).Replace(
        '__VIDEO_SIZE_BYTES__', [string]$resolvedVideoSize
    )
} else {
    $fixtureSql = (Get-Content -LiteralPath $genericSql -Raw).
        Replace('__PREVIOUS_LESSON_ID__', [string]$previousLessonId).
        Replace('__VIDEO_SIZE_BYTES__', [string]$resolvedVideoSize).
        Replace('__LESSON_ID__', [string]$LessonId).
        Replace('__UPLOAD_ID__', $UploadId).
        Replace('__RUN_ID__', $runId)
}

function Expand-IamTemplate([string]$Path) {
    return (Get-Content -LiteralPath $Path -Raw).
        Replace('${ACCOUNT_ID}', $AccountId).
        Replace('${MEDIACONVERT_QUEUE_NAME}', $MediaConvertQueueName).
        Replace('__LESSON_ID__', [string]$LessonId).
        Replace('__RUN_ID__', $runId)
}

$k4Policy = Expand-IamTemplate $k4PolicyTemplate
$k5Policy = Expand-IamTemplate $k5PolicyTemplate
$mediaConvertPolicy = Expand-IamTemplate $mediaConvertPolicyTemplate

[void]($asl | ConvertFrom-Json)
[void]($k4Policy | ConvertFrom-Json)
[void]($k5Policy | ConvertFrom-Json)
[void]($mediaConvertPolicy | ConvertFrom-Json)
if ($asl -match '\$\{TEST_' -or $fixtureSql -match '__[A-Z0-9_]+__' -or
    $k4Policy -match '__|\$\{' -or $k5Policy -match '__|\$\{' -or
    $mediaConvertPolicy -match '__|\$\{') {
    throw 'One or more template placeholders remain unresolved.'
}

$aslPath = Join-Path $output 'k4-k5-e2e-test.rendered.asl.json'
$inputPath = Join-Path $output "k4-k5-e2e-lesson-$LessonId-input.rendered.json"
$sqlPath = Join-Path $output "add-k4-k5-e2e-lesson-$LessonId-fixture.rendered.sql"
$k4PolicyPath = Join-Path $output 'k4-e2e-test-lambda-permissions.rendered.json'
$k5PolicyPath = Join-Path $output 'k5-e2e-test-lambda-permissions.rendered.json'
$mediaConvertPolicyPath = Join-Path $output 'mediaconvert-k5-e2e-test-permissions.rendered.json'
$manifestPath = Join-Path $output "k4-k5-e2e-lesson-$LessonId-manifest.json"
$utf8 = [System.Text.UTF8Encoding]::new($false)

[System.IO.File]::WriteAllText($aslPath, $asl, $utf8)
[System.IO.File]::WriteAllText($sqlPath, $fixtureSql, $utf8)
[System.IO.File]::WriteAllText($k4PolicyPath, $k4Policy, $utf8)
[System.IO.File]::WriteAllText($k5PolicyPath, $k5Policy, $utf8)
[System.IO.File]::WriteAllText($mediaConvertPolicyPath, $mediaConvertPolicy, $utf8)

$manifest = [ordered]@{
    lesson_id = $LessonId
    upload_id = $UploadId
    attempt = 0
    run_id = $runId
    raw_key = $rawKey
    output_key = $outputKey
    transcript_key = $transcriptKey
    transcribe_job_name = "learncloud-k5-$runId"
    video_size_bytes = $resolvedVideoSize
}
[System.IO.File]::WriteAllText(
    $manifestPath, ($manifest | ConvertTo-Json -Depth 3), $utf8
)

$rendered = @(
    $aslPath, $sqlPath, $k4PolicyPath, $k5PolicyPath,
    $mediaConvertPolicyPath, $manifestPath
)
if ($PSBoundParameters.ContainsKey('S3ETag')) {
    $inputJson = (Get-Content -LiteralPath $inputTemplate -Raw).
        Replace('__LESSON_ID__', [string]$LessonId).
        Replace('__UPLOAD_ID__', $UploadId).
        Replace('__S3_ETAG_WITHOUT_QUOTES__', $S3ETag.ToLowerInvariant())
    [void]($inputJson | ConvertFrom-Json)
    if ($inputJson -match '__[A-Z0-9_]+__') {
        throw 'The input template placeholder remains unresolved.'
    }
    [System.IO.File]::WriteAllText($inputPath, $inputJson, $utf8)
    $rendered += $inputPath
}

Get-FileHash -Algorithm SHA256 -LiteralPath $rendered |
    Select-Object Path, Hash
