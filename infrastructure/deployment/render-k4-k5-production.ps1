[CmdletBinding()]
param(
    [ValidatePattern('^\d{12}$')]
    [string]$AccountId = '697589240877',

    [string]$PipelineLambdaArn = 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-pipeline',

    [string]$AiWorkerLambdaArn = 'arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-ai-worker',

    [string]$StateMachineArn = 'arn:aws:states:ap-southeast-1:697589240877:stateMachine:learncloud-video-pipeline',

    [ValidatePattern('^[A-Za-z0-9_-]+$')]
    [string]$MediaConvertQueueName,

    [string]$MediaConvertRoleArn,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pipelinePattern = "^arn:aws:lambda:ap-southeast-1:${AccountId}:function:learncloud-video-pipeline$"
$workerPattern = "^arn:aws:lambda:ap-southeast-1:${AccountId}:function:learncloud-ai-worker$"
$stateMachinePattern = "^arn:aws:states:ap-southeast-1:${AccountId}:stateMachine:learncloud-video-pipeline$"
$mediaRolePattern = "^arn:aws:iam::${AccountId}:role/[A-Za-z0-9_+=,.@/\-]+$"

if ($PipelineLambdaArn -notmatch $pipelinePattern) {
    throw 'PipelineLambdaArn must name the exact production K4 Lambda.'
}
if ($AiWorkerLambdaArn -notmatch $workerPattern) {
    throw 'AiWorkerLambdaArn must name the exact production K5 Lambda.'
}
if ($StateMachineArn -notmatch $stateMachinePattern) {
    throw 'StateMachineArn must name the exact production state machine.'
}
$hasQueue = -not [string]::IsNullOrWhiteSpace($MediaConvertQueueName)
$hasMediaRole = -not [string]::IsNullOrWhiteSpace($MediaConvertRoleArn)
if ($hasQueue -ne $hasMediaRole) {
    throw 'Supply both MediaConvertQueueName and MediaConvertRoleArn, or neither.'
}
if ($hasMediaRole -and $MediaConvertRoleArn -notmatch $mediaRolePattern) {
    throw 'MediaConvertRoleArn must be an IAM role in the production account.'
}

$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) {
    throw "Output directory already exists: $output"
}
[void](New-Item -ItemType Directory -Path $output)
$utf8 = [Text.UTF8Encoding]::new($false)

function Render-File([string]$Source, [string]$Destination) {
    $content = Get-Content -Raw -LiteralPath (Join-Path $repoRoot $Source)
    $content = $content.Replace('${ACCOUNT_ID}', $AccountId).
        Replace('${PIPELINE_LAMBDA_ARN}', $PipelineLambdaArn).
        Replace('${AI_WORKER_ARN}', $AiWorkerLambdaArn).
        Replace('${STATE_MACHINE_ARN}', $StateMachineArn)
    if ($hasQueue) {
        $content = $content.Replace('${MEDIACONVERT_QUEUE_NAME}', $MediaConvertQueueName).
            Replace('${MEDIACONVERT_ROLE_ARN}', $MediaConvertRoleArn)
    }
    [void]($content | ConvertFrom-Json)
    if ($content -match '\$\{') {
        throw "Unresolved placeholder in $Source"
    }
    $path = Join-Path $output $Destination
    [IO.File]::WriteAllText($path, $content, $utf8)
    return $path
}

$rendered = @()
$rendered += Render-File 'infrastructure\step-functions\video_pipeline.asl.json' 'video_pipeline.production.asl.json'
$rendered += Render-File 'infrastructure\iam\step-functions-permissions.json' 'step-functions-permissions.production.json'
$rendered += Render-File 'infrastructure\iam\lambda-ai-worker-permissions.json' 'ai-worker-permissions.production.json'
$rendered += Render-File 'infrastructure\iam\eventbridge-permissions.json' 'eventbridge-permissions.production.json'
$rendered += Render-File 'infrastructure\iam\step-functions-trust.json' 'step-functions-trust.production.json'
$rendered += Render-File 'infrastructure\iam\eventbridge-trust.json' 'eventbridge-trust.production.json'
$rendered += Render-File 'infrastructure\eventbridge\s3-object-created.pattern.json' 'video-upload.pattern.production.json'
$rendered += Render-File 'infrastructure\eventbridge\retry.pattern.json' 'video-retry.pattern.production.json'
$rendered += Render-File 'infrastructure\eventbridge\execution-failure.pattern.json' 'execution-failure.pattern.production.json'
$rendered += Render-File 'infrastructure\eventbridge\s3-input-transformer.json' 's3-input-transformer.production.json'
$rendered += Render-File 'infrastructure\iam\mediaconvert-permissions.json' 'mediaconvert-permissions.production.json'
if ($hasQueue) {
    $rendered += Render-File 'infrastructure\iam\lambda-pipeline-permissions.json' 'pipeline-permissions.production.json'
}

$manifest = [ordered]@{
    account_id = $AccountId
    region = 'ap-southeast-1'
    pipeline_lambda_arn = $PipelineLambdaArn
    ai_worker_lambda_arn = $AiWorkerLambdaArn
    state_machine_arn = $StateMachineArn
    media_convert_queue_name = if ($hasQueue) { $MediaConvertQueueName } else { $null }
    media_convert_role_arn = if ($hasMediaRole) { $MediaConvertRoleArn } else { $null }
    pipeline_policy_rendered = $hasQueue
    activation_flags = [ordered]@{
        k4_video_pipeline_enabled = $true
        k4_video_ai_enabled = $false
        k5_ai_worker_enabled = $false
    }
}
$manifestPath = Join-Path $output 'production-manifest.json'
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5), $utf8)
$rendered += $manifestPath

Get-FileHash -Algorithm SHA256 -LiteralPath $rendered |
    Select-Object Path, Hash
