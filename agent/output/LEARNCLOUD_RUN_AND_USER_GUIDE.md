# LearnCloud — hướng dẫn chạy và sử dụng trên Windows 11

Cập nhật: **09/11/2026 (Asia/Saigon)**. Đối chiếu source trong workspace, gồm bản sửa Authorization P0 hiện có. Các lệnh dưới đây dành cho **người đọc tự thực hiện**; khi viết tài liệu, không cài đặt, không khởi động database, không sửa cấu hình và không kết nối AWS/RDS.

## 1. Đọc phần này trước khi chạy

Repository hiện có React/Vite, FastAPI, PostgreSQL và các adapter/workflow AWS. **Không có một chế độ local đầy đủ tất cả chức năng mà không cần Cognito.**

- Backend xác thực Cognito JWT. POST /auth/login đã bỏ; X-Demo-User không đăng nhập được. Script đặt password local cũ không thay thế Cognito.
- **users.role trong PostgreSQL quyết định quyền.** Cognito group không tự cấp INSTRUCTOR/ADMIN hoặc khôi phục role đã bị hạ. Admin đầu tiên phải được người phụ trách chuẩn bị đúng Cognito sub và DB role; không có tài khoản Admin/mật khẩu mặc định được hướng dẫn này cung cấp.
- Backend đọc **.env ở root repository** qua backend/app/config.py. Frontend đọc **frontend/.env**. backend/.env không phải file Settings hiện dùng.
- Root .env.example có **hai dòng DATABASE_URL**, trong đó có mẫu RDS/tunnel. Phải thay thành **một dòng đúng môi trường**; không copy nguyên rồi mặc định cho rằng đang dùng Docker.
- README/docs/local-setup.md còn thông tin cũ về demo header/local JWT và router chưa đăng ký. Source hiện có 68 cặp method/path, gồm Progress, Quiz, Tutor, Review và Admin.
- Có xung đột migration version 0004. Không dùng vòng lặp “apply mọi migration” từ tài liệu cũ. Bước schema local ở mục 7.3 là prerequisite thật, không được bỏ qua.
- “Đã có code”, “unit test đạt” và “đã chạy end-to-end trên AWS” là ba mức bằng chứng khác nhau.

## 2. Chọn đúng môi trường

| Trường hợp | Frontend | Backend/DB | Đăng nhập | Có thể thử và giới hạn |
|---|---|---|---|---|
| **A — Frontend mock, chưa có AWS** | VITE_USE_MOCK=true; VITE_USE_AUTH_MOCK=true | Không cần | Tự đăng ký **STUDENT mô phỏng** trong browser | Catalog/enroll/video mẫu/flashcards/progress/checkpoint mock. Không có Instructor/Admin mock chính thức. Tutor và trang hoàn thành course vẫn gọi API thật, nên chưa dùng được với mock token. |
| **B — Frontend + Backend + PostgreSQL local** | Cả hai mock=false để dùng dữ liệu thật | PostgreSQL Docker, schema phù hợp source | **Vẫn cần Cognito thật** cho API có bảo vệ | CRUD, enroll, quiz/read models theo code; video cần S3, AI/pipeline cần AWS. Nếu chưa có Cognito, chỉ kiểm health/OpenAPI và public API với DB đã chuẩn bị; không dùng mock token gọi Backend thật. |
| **C — tích hợp AWS** | Cả hai mock=false; URL API đúng deployment | Backend local hoặc Lambda; DB test/RDS được phép | Cognito cùng pool/client với Backend | Thêm S3, EventBridge/Step Functions/MediaConvert/Transcribe/Bedrock và worker đã triển khai. Các luồng này chưa được tài liệu này chứng nhận E2E. |

Có thể dùng **Cognito thật + nội dung Student mock**: VITE_USE_AUTH_MOCK=false, VITE_USE_MOCK=true. Đây là chế độ pha trộn, không phải demo toàn hệ thống; các trang quản lý/Tutor vẫn gọi API thật và có thể lệch dữ liệu/ID mock.

**Không dùng tổ hợp VITE_USE_AUTH_MOCK=true, VITE_USE_MOCK=false.** Frontend chủ động từ chối gửi token mô phỏng vào API thật.

## 3. Phần mềm và thư mục

### 3.1. Cài phần mềm

Mở PowerShell trên Windows 11. Chỉ chạy dòng dành cho phần mềm còn thiếu; mở terminal mới sau khi cài.

~~~powershell
winget install --exact --id Git.Git
winget install --exact --id Python.Python.3.12
winget install --exact --id OpenJS.NodeJS.LTS
winget install --exact --id Docker.DockerDesktop
~~~

- **Python 3.12 x64** phù hợp môi trường đã chạy kiểm thử và các dependency đã pin. Không mặc định dùng bản Python mới nhất cho requirements cũ.
- Node phải đáp ứng engines trong frontend/package-lock.json: **^20.19.0 hoặc >=22.12.0**. Chọn bản **LTS còn được hỗ trợ**, không chỉ thỏa số phiên bản tối thiểu. [Lịch phát hành Node.js](https://github.com/nodejs/Release).
- Docker Desktop chạy **Linux containers**, với backend Windows/WSL phù hợp. Nếu cần WSL2, trong PowerShell Administrator:

~~~powershell
wsl --status
# Chỉ cài nếu chưa có; khởi động lại Windows nếu được yêu cầu.
wsl --install
wsl --update
~~~

Sau đó mở Docker Desktop, chờ Engine running. Xem [hướng dẫn Docker Windows](https://docs.docker.com/desktop/setup/install/windows-install/).

Kiểm tra:

~~~powershell
git --version
py -3.12 --version
node --version
npm.cmd --version
docker --version
docker compose version
~~~

**Chỉ chế độ AWS mới cần AWS CLI v2**, và SSH/Session Manager plugin nếu nhóm dùng tunnel. Không cần cài PostgreSQL server riêng trên Windows khi dùng Compose; psql có trong container.

~~~powershell
winget install --exact --id Amazon.AWSCLI
aws --version
~~~

Nguồn cài AWS CLI: [AWS CLI v2 trên Windows](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

### 3.2. Về đúng root repository

Nếu đã có source, không clone đè lên nó. Đường dẫn dưới đây là workspace hiện tại; đổi đường dẫn nếu máy của bạn clone ở nơi khác.

~~~powershell
Set-Location -LiteralPath 'D:\projects\main projects\AWS-CLOUD'
$learnCloudRoot = (Get-Location).Path
Test-Path .\backend\requirements.txt
Test-Path .\frontend\package.json
Test-Path .\docker-compose.yml
~~~

Ba lệnh Test-Path phải trả True. Các terminal mới không tự có biến $learnCloudRoot hoặc các function của terminal trước.

## 4. Hàm hỗ trợ cấu hình: chạy một lần trong terminal thiết lập

Hàm này cập nhật một key và loại các dòng key trùng; không in giá trị ra màn hình. Nó **chỉ chạy khi bạn copy lệnh**, không được thực thi khi tài liệu được tạo. Không chia sẻ nội dung .env.

~~~powershell
function Set-LearnCloudEnvValue {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Key,
        [AllowEmptyString()][string]$Value
    )
    $contentLines = @()
    if (Test-Path -LiteralPath $Path) {
        $contentLines = @([System.IO.File]::ReadAllLines($Path))
    }
    $keyPattern = '^\s*' + [regex]::Escape($Key) + '\s*='
    $contentLines = @($contentLines | Where-Object { $_ -notmatch $keyPattern })
    $contentLines += "$Key=$Value"
    [System.IO.File]::WriteAllLines(
        $Path, [string[]]$contentLines, [System.Text.UTF8Encoding]::new($false)
    )
}
~~~

Giữ function trong cùng terminal khi chạy các mục cấu hình. VITE_* được đưa vào mã phía trình duyệt: chỉ chứa API URL, các ID Cognito công khai và flag. **Không đặt DB password, AWS access key/secret, token hoặc client secret vào VITE_*.** Vite nạp .env.local/mode và biến process có thể ghi đè .env; đổi file cần restart Vite. [Quy tắc env của Vite](https://vite.dev/guide/env-and-mode.html).

## 5. Cách chạy nhanh A — Student mock, không AWS/Backend

### 5.1. Cài dependencies Frontend

Từ root:

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
Set-Location .\frontend
npm.cmd ci
npm.cmd ls react react-dom react-router-dom vite aws-amplify --depth=0
Set-Location -LiteralPath $learnCloudRoot
~~~

Có package-lock.json nên ưu tiên npm ci. Chỉ dùng npm install khi người phụ trách chủ ý cập nhật dependencies/lockfile; không tự nâng riêng aws-amplify hoặc Vite để chữa một lỗi đường dẫn.

### 5.2. Tạo/chỉnh frontend/.env cho mock

Không ghi đè file đã có; chỉ chỉnh các key cần dùng.

~~~powershell
$frontendEnv = Join-Path $learnCloudRoot 'frontend\.env'
if (-not (Test-Path -LiteralPath $frontendEnv)) {
    Copy-Item -LiteralPath (Join-Path $learnCloudRoot 'frontend\.env.example') -Destination $frontendEnv
}
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_API_URL -Value 'http://127.0.0.1:8000'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_API_BASE_URL -Value 'http://127.0.0.1:8000'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_MOCK -Value 'true'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_AUTH_MOCK -Value 'true'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_COGNITO_USER_POOL_ID -Value ''
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_COGNITO_APP_CLIENT_ID -Value ''
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_MOCK_COMPLETION_PERCENT -Value '10'
~~~

VITE_API_BASE_URL có ưu tiên cao hơn VITE_API_URL trong frontend/src/api/client.js; ở đây đặt cùng giá trị để tránh URL cũ thắng. Backend không cần bật cho các chức năng Student đã có adapter mock.

VITE_MOCK_COMPLETION_PERCENT=10 là ngưỡng xem video phục vụ thử nhanh; đổi thành 95 nếu muốn demo ngưỡng cao hơn. Đây **chỉ là rule mock**, không sửa completion rule của Backend.

### 5.3. Chạy Vite, đăng ký tài khoản mô phỏng

~~~powershell
Set-Location -LiteralPath (Join-Path $learnCloudRoot 'frontend')
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
~~~

Trong browser mở http://127.0.0.1:5173/login. Dùng nhất quán một origin; localhost và 127.0.0.1 có browser storage khác nhau.

1. Bấm **Đăng ký tài khoản học viên**, nhập thông tin và **mật khẩu thử do bạn tự chọn**, ít nhất 8 ký tự, gồm chữ và số. Không nhập mật khẩu tài khoản thật.
2. Trang **Xác minh email** không gửi email thật. Với mock, mở DevTools → Application → Local Storage của đúng origin → key **learncloud.mock.accounts.v1** → codes → bản ghi verify của email vừa đăng ký → đọc trường code và nhập vào UI. Nếu mã hết hạn, chờ hết cooldown rồi bấm Gửi lại mã và đọc bản ghi mới. Không đưa giá trị code/password/storage vào báo cáo hoặc ảnh chụp chia sẻ.
3. Xác minh xong, quay lại **Đăng nhập**, dùng thông tin vừa tự đăng ký.
4. Mở **Khám phá khóa học**, chọn một course trong dữ liệu mẫu, enroll rồi học. Video mẫu được phục vụ từ frontend/public/cloud.mp4, không phải S3.
5. Student mock là vai trò duy nhất do account.mock.js trả về. Không có nút hoặc tài khoản seed Instructor/Admin mock được chứng minh trong source. Muốn thử hai vai trò đó, chuyển sang đăng nhập thật và DB đã provision.

Mock accounts/enrollment/watch ranges/ratings/history nằm trong browser storage, tách theo user. Draft quiz dùng sessionStorage; không bảo đảm đồng bộ thiết bị/tab khác. Đăng xuất và đăng nhập account khác để kiểm tra cách ly; không dùng sửa role trong storage làm bằng chứng Backend authorization.

## 6. Chuẩn bị Python/Backend

Chế độ A không cần phần này. Chế độ B/C mở terminal tại root:

~~~powershell
Set-Location -LiteralPath 'D:\projects\main projects\AWS-CLOUD'
$learnCloudRoot = (Get-Location).Path
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    py -3.12 -m venv .venv
}
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe -m pip check
~~~

Có thể activate bằng lệnh sau; toàn bộ hướng dẫn vẫn gọi python.exe theo đường dẫn nên **không bắt buộc activate**:

~~~powershell
.\.venv\Scripts\Activate.ps1
~~~

Nếu bị ExecutionPolicy chặn, bỏ bước activate, tiếp tục dùng .venv\Scripts\python.exe; không cần đổi policy toàn máy.

requirements.txt gồm FastAPI/Uvicorn, SQLAlchemy, psycopg2-binary, pg8000, Pydantic, boto3, PyJWT[crypto], httpx, Mangum… **pytest không nằm trong runtime requirements**; xem mục 14 nếu muốn chạy test.

## 7. Chạy B — PostgreSQL local và FastAPI

### 7.1. Chạy PostgreSQL Docker

Mở Docker Desktop trước. Từ root:

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
docker compose up -d learncloud-db
docker compose ps
docker compose logs --tail 50 learncloud-db
docker exec learncloud-db pg_isready -U learncloud -d learncloud
Test-NetConnection -ComputerName 127.0.0.1 -Port 5434
~~~

Compose hiện có duy nhất service **learncloud-db**, image **postgres:16**, container **learncloud-db**, database/user **learncloud**, mapping **host 5434 → container 5432**, volume **learncloud_data**. Compose không khởi động FastAPI, React hoặc AI worker.

### 7.2. Đặt một DATABASE_URL local duy nhất, không in password

Chạy lại hàm mục 4 nếu là terminal mới. Mật khẩu được đọc từ cấu hình Compose vào biến, không ghi giá trị vào hướng dẫn.

~~~powershell
$backendEnv = Join-Path $learnCloudRoot '.env'
if (-not (Test-Path -LiteralPath $backendEnv)) {
    Copy-Item -LiteralPath (Join-Path $learnCloudRoot '.env.example') -Destination $backendEnv
}
$composeSettings = docker compose config --format json | ConvertFrom-Json
$localPgSettings = $composeSettings.services.'learncloud-db'.environment
$localEncodedPassword = [Uri]::EscapeDataString([string]$localPgSettings.POSTGRES_PASSWORD)
$localDatabaseUrl = "postgresql+psycopg2://$($localPgSettings.POSTGRES_USER):$($localEncodedPassword)@127.0.0.1:5434/$($localPgSettings.POSTGRES_DB)"
Set-LearnCloudEnvValue -Path $backendEnv -Key DATABASE_URL -Value $localDatabaseUrl
Set-LearnCloudEnvValue -Path $backendEnv -Key APP_ENV -Value 'development'
Set-LearnCloudEnvValue -Path $backendEnv -Key ALLOW_RAW_VIDEO_PLAYBACK -Value 'false'
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_PIPELINE_ENABLED -Value 'false'
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_PROCESSOR_BACKEND -Value 'disabled'
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_AI_ENABLED -Value 'false'
Remove-Variable composeSettings,localPgSettings,localEncodedPassword,localDatabaseUrl
~~~

Password trong volume Docker đã tạo trước đây **không tự đổi** chỉ vì sửa Compose. Không xóa volume để thử sửa lỗi authentication. JWT_SECRET_KEY trong template là dấu vết local auth cũ; nó không thay pool/client/JWKS của Cognito hiện tại.

### 7.3. Chuẩn bị schema — prerequisite đang cần nhóm chốt

**Container healthy chưa có nghĩa schema LearnCloud đã đủ.** Database mới từ image không tự chạy database/schema.sql hoặc seed.sql: Compose không mount thư mục init SQL.

Các vấn đề hiện tại:

- Bốn script cùng version 0004: add_lesson_approved_status, checkpoint_attempt_idempotency, cognito_auth_cutover, remove_approved_lesson_status.
- 0005 yêu cầu description/version đúng của nhánh remove APPROVED; không thể coi chạy mọi file 0004 theo tên là an toàn.
- ORM hiện cần courses.cover_image, tutor_sessions.workflow_state, practice_questions/remediation_completed, quiz_attempts.request_id/request_hash, checkpoint_remediation và ledger nếu bật pipeline. Chỉ schema.sql + 0003 + seed theo hướng dẫn cũ không đủ.
- Có cả migrations dạng V1/V2/V3 và 0003/0004/0005/0006. Không dùng glob chọn một nhóm rồi giả định đã đầy đủ.
- Seed cũ không tạo tài khoản Cognito đăng nhập được. Không có password đăng nhập thật nào được suy từ email seed.

Kiểm tra local **chỉ đọc**:

~~~powershell
docker exec learncloud-db psql -U learncloud -d learncloud -c "\dt"
docker exec learncloud-db psql -U learncloud -d learncloud -c "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('courses','tutor_sessions','quiz_attempts','checkpoint_remediation','video_uploads','video_pipeline_runs') ORDER BY table_name,ordinal_position;"
~~~

**Thành viên mới cần nhận schema/snapshot local đã được người phụ trách DB duyệt** hoặc kế hoạch migrations đã hợp nhất. Repository hiện chưa có một lệnh bootstrap mới đủ an toàn để khẳng định hoàn thiện mọi module. Đừng tự đánh dấu step này đạt nếu còn thiếu cột/bảng.

Nếu nhóm đã cấp một file SQL bootstrap/snapshot local được duyệt, có thể tự nạp bằng lệnh dưới đây. Đường dẫn được nhập là file do nhóm cấp, **không phải file mới được bịa rằng có sẵn trong repository**. Chỉ dùng cho container local này, không dùng cho RDS/shared DB:

~~~powershell
$approvedLocalSql = Read-Host 'Duong dan tuyet doi file SQL local da duoc DB owner duyet'
if (-not (Test-Path -LiteralPath $approvedLocalSql -PathType Leaf)) {
    throw 'Khong tim thay SQL da duyet; dung buoc nay.'
}
Get-Content -LiteralPath $approvedLocalSql -Raw -Encoding UTF8 |
    docker exec -i learncloud-db psql -v ON_ERROR_STOP=1 -U learncloud -d learncloud
if ($LASTEXITCODE -ne 0) { throw 'Nap SQL that bai; khong tiep tuc demo.' }
~~~

Tài liệu này không chạy lệnh trên, không tự chọn/apply migration và không cung cấp shortcut bỏ registry/triggers. Khi chưa có schema đã duyệt, dùng **A** để demo Student; vẫn có thể mở Backend health/Swagger ở mục sau.

### 7.4. Chạy FastAPI từ root

Đảm bảo DATABASE_URL trỏ local như mục 7.2. Với PowerShell mở riêng, cần đặt lại thư mục root:

~~~powershell
Set-Location -LiteralPath 'D:\projects\main projects\AWS-CLOUD'
Remove-Item Env:AWS_LAMBDA_FUNCTION_NAME -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
~~~

Biến process có ưu tiên cao hơn root .env: dòng Remove-Item DATABASE_URL phía trên chỉ xóa giá trị kế thừa của terminal để dùng file local vừa cấu hình; không xóa file hay database. Không chạy app.main từ root mà thiếu --app-dir backend. main.py thêm repository root để import ai_pipeline. Không đổi thành một app/FastAPI thử nghiệm khác rồi nghĩ đang xem LearnCloud.

Trong terminal khác:

~~~powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
$openApi = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json'
$openApi.info | Select-Object title,version
$openApi.paths.PSObject.Properties.Name | Where-Object { $_ -like '/tutor/*' }
Start-Process 'http://127.0.0.1:8000/docs'
~~~

Kỳ vọng health status=ok, title LearnCloud, có đủ 3 Tutor POST. **Health không probe DB**. Chỉ sau khi schema sẵn sàng mới kiểm public catalog:

~~~powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/courses'
~~~

Array rỗng có thể là chưa có course PUBLISHED. Lỗi missing column là schema chưa phù hợp; không chữa bằng demo identity hoặc bỏ guard.

## 8. Cấu hình đăng nhập Cognito thật cho B/C

### 8.1. Nhận cấu hình từ người phụ trách AWS

Cần **Region, User Pool ID, App Client ID** đúng môi trường test và một tài khoản/luồng đăng ký được phép. Không lấy ARN, pool ID, endpoint, user/password từ ví dụ trong báo cáo cũ.

Kiểm tra bằng Console và/hoặc các lệnh đọc cấu hình dưới đây:

- App client loại **public/SPA, không có client secret**: frontend không gửi SECRET_HASH. [AWS: public app client](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html).
- Frontend gọi USER_PASSWORD_AUTH; client phải bật **ALLOW_USER_PASSWORD_AUTH**, cấu hình refresh phù hợp Amplify. [AWS: authentication flows](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html).
- Email signup/verification, thuộc tính name/email và chính sách password phải phù hợp form. Nếu pool yêu cầu MFA/challenge đổi mật khẩu tạm, UI hiện chỉ báo chưa hoàn tất; chưa có đủ màn challenge.
- Admin đầu tiên đã có Cognito sub liên kết users.role=ADMIN trong DB do luồng được duyệt. Tự thêm group ADMIN ở Cognito không đủ.
- Backend local cần đi được tới JWKS của đúng pool. Sau login, /auth/me phải tìm thấy user qua sub; account tạo chỉ trên Cognito Console có thể thiếu DB mapping/email claim. Dùng verify-email/provision đúng luồng, không tự chọn user ID.
- Backend signup/OTP/reset/admin dùng Cognito SDK. Riêng verify-email còn gọi admin_get_user để đồng bộ DB, nên AWS credentials/IAM phía Backend cũng cần đúng; đăng nhập bằng Amplify không tự cấp IAM credentials cho server.

### 8.2. AWS CLI profile, chỉ kiểm tra cấu hình

Nếu tổ chức dùng IAM Identity Center/SSO:

~~~powershell
$awsProfileName = Read-Host 'Ten AWS CLI profile duoc nhom cap'
aws configure sso --profile $awsProfileName
aws sso login --profile $awsProfileName
$awsRegionName = Read-Host 'AWS Region dung cua moi truong test'
$cognitoPoolId = Read-Host 'Cognito User Pool ID dung'
$cognitoClientId = Read-Host 'Cognito App Client ID dung'

aws cognito-idp describe-user-pool --profile $awsProfileName --region $awsRegionName --user-pool-id $cognitoPoolId --query "UserPool.{Id:Id,AutoVerifiedAttributes:AutoVerifiedAttributes,UsernameAttributes:UsernameAttributes}" --output json
aws cognito-idp describe-user-pool-client --profile $awsProfileName --region $awsRegionName --user-pool-id $cognitoPoolId --client-id $cognitoClientId --query "UserPoolClient.{ClientId:ClientId,ExplicitAuthFlows:ExplicitAuthFlows,ReadAttributes:ReadAttributes,WriteAttributes:WriteAttributes}" --output json
aws cognito-idp describe-user-pool-client --profile $awsProfileName --region $awsRegionName --user-pool-id $cognitoPoolId --client-id $cognitoClientId --query "contains(keys(UserPoolClient), 'ClientSecret')" --output text
~~~

Lệnh cuối chỉ in cờ có secret, không in secret. Source hiện cần public client không secret; nếu không phù hợp, nhờ AWS owner cấu hình client test đúng, không nhét secret vào Vite. Các lệnh trên không tự tạo/sửa pool/client. [AWS CLI describe-user-pool-client](https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/describe-user-pool-client.html).

Nếu nhóm không dùng SSO, sử dụng profile/credential chain đã được cấp theo quy trình của nhóm; không ghi access key/secret vào file hướng dẫn hoặc frontend env.

### 8.3. Đặt Settings Backend và frontend cùng pool/client

Tại terminal đã có hàm mục 4 và các biến vừa nhập:

~~~powershell
$backendEnv = Join-Path $learnCloudRoot '.env'
$frontendEnv = Join-Path $learnCloudRoot 'frontend\.env'

Set-LearnCloudEnvValue -Path $backendEnv -Key AWS_REGION -Value $awsRegionName
Set-LearnCloudEnvValue -Path $backendEnv -Key COGNITO_REGION -Value $awsRegionName
Set-LearnCloudEnvValue -Path $backendEnv -Key COGNITO_USER_POOL_ID -Value $cognitoPoolId
Set-LearnCloudEnvValue -Path $backendEnv -Key COGNITO_APP_CLIENT_ID -Value $cognitoClientId

Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_AWS_REGION -Value $awsRegionName
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_COGNITO_USER_POOL_ID -Value $cognitoPoolId
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_COGNITO_APP_CLIENT_ID -Value $cognitoClientId
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_AUTH_MOCK -Value 'false'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_MOCK -Value 'false'
~~~

Trong **terminal chạy Backend**, export profile/region trước khi khởi động Uvicorn:

~~~powershell
$env:AWS_PROFILE = Read-Host 'Ten AWS CLI profile da dang nhap'
$env:AWS_REGION = Read-Host 'AWS Region dung'
$env:AWS_DEFAULT_REGION = $env:AWS_REGION
Remove-Item Env:AWS_LAMBDA_FUNCTION_NAME -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
~~~

Không coi AWS_PROFILE đặt trong .env là đã export cho boto3: Pydantic Settings không tự đưa mọi key vào os.environ. Tương tự, BEDROCK_MODEL_ID/TUTOR_USE_BEDROCK được code đọc bằng os.getenv; nếu dùng, cần export vào process đúng terminal, không chỉ ghi key không thuộc Settings.

### 8.4. Kiểm thử đăng nhập thật

1. Restart Backend và Vite; mở /register → /verify-email → /login hoặc dùng account test do nhóm cấp.
2. Mở DevTools Network: signIn đi Cognito, sau đó **GET /auth/me** đi Backend và phải 200. Không có POST /auth/login ở Backend.
3. Dùng **Access Token**, không dùng ID Token khi Authorize Swagger. Không chụp/log/chia sẻ token.
4. Kiểm role từ /auth/me; nếu sai role, kiểm mapping users.role/sub với người phụ trách, không thử X-Demo-User.
5. Có thể kiểm bằng PowerShell mà không in token:

~~~powershell
$apiBase = 'http://127.0.0.1:8000'
$secureAccessToken = Read-Host 'Access token cua chinh tai khoan test (khong hien thi)' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAccessToken)
try {
    $requestHeaders = @{ Authorization = 'Bearer ' + [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer) }
    $myIdentity = Invoke-RestMethod -Uri "$apiBase/auth/me" -Headers $requestHeaders
    $myIdentity | Select-Object id,role
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    Remove-Variable secureAccessToken,tokenPointer,requestHeaders,myIdentity -ErrorAction SilentlyContinue
}
~~~

Chỉ dùng token được cấp hợp lệ cho tài khoản test của bạn. 401 ở /auth/me có thể là pool/client sai, hết hạn, thiếu DB mapping hoặc identity sub không khớp; 403 ở API quản lý là role/ownership, không tự động là lỗi đăng nhập.

## 9. Chạy Frontend dùng API thật

Từ terminal cấu hình đã có hàm mục 4:

~~~powershell
$frontendEnv = Join-Path $learnCloudRoot 'frontend\.env'
$learnCloudApiUrl = Read-Host 'API base URL that, khong them /docs hay /openapi.json'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_API_URL -Value $learnCloudApiUrl.TrimEnd('/')
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_API_BASE_URL -Value $learnCloudApiUrl.TrimEnd('/')
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_MOCK -Value 'false'
Set-LearnCloudEnvValue -Path $frontendEnv -Key VITE_USE_AUTH_MOCK -Value 'false'
Set-Location -LiteralPath (Join-Path $learnCloudRoot 'frontend')
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
~~~

Với Backend local nhập http://127.0.0.1:8000. Với API Gateway, nhập chính xác invoke base URL/stage của nhóm; Mangum hiện cấu hình base path /default, không tự suy mọi stage đều tương thích. Backend CORS hiện chỉ cho localhost:5173 và 127.0.0.1:5173; --strictPort tránh Vite tự nhảy 5174.

Kiểm tra build/preview khi cần, **không phải khởi động Backend**:

~~~powershell
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 5173 --strictPort
~~~

Build dùng env tại thời điểm build; đổi env phải build lại. Preview chỉ dùng khi dev server ở 5173 đã dừng.

## 10. Tích hợp C — RDS, S3 và AI Pipeline

### 10.1. Đổi kết nối sang RDS test được phép

Chỉ làm khi nhóm cấp **RDS test/staging**, DB name/user, đường mạng/VPN/tunnel và CA certificate. Không dùng báo cáo này để kết nối hoặc migrate production. Trước khi đổi DB, dừng Uvicorn.

- Desktop Backend dùng **DATABASE_URL** trong root .env hoặc biến process; DB_HOST/DB_USER/DB_NAME không thay DATABASE_URL ở nhánh desktop.
- Chỉ khi AWS_LAMBDA_FUNCTION_NAME tồn tại, database.py dùng DB_HOST, DB_USER, DB_NAME, DB_PORT và DB_PASSWORD hoặc SSM parameter. Đừng set biến Lambda chỉ để test local.
- RDS private cần VPN hoặc bastion/SSM đã được nhóm chuẩn bị; app/pip không tự mở được Security Group.

Kiểm tra TCP trên RDS test sau khi xác nhận quyền:

~~~powershell
$rdsHostName = Read-Host 'Endpoint DNS RDS test do nhom cap'
Test-NetConnection -ComputerName $rdsHostName -Port 5432
~~~

Nếu dùng SSH tunnel qua bastion được cấp, mở **terminal riêng và giữ mở**; không cần làm RDS public:

~~~powershell
$rdsHostName = Read-Host 'Endpoint DNS RDS test'
$bastionHostName = Read-Host 'Hostname bastion duoc cap'
$bastionUserName = Read-Host 'SSH user duoc cap'
$bastionKeyFile = Read-Host 'Duong dan private key SSH cua ban'
ssh -N -i $bastionKeyFile -L "127.0.0.1:15437:$($rdsHostName):5432" "$($bastionUserName)@$($bastionHostName)"
~~~

Nếu nhóm dùng Session Manager thay SSH, dùng instance/profile/document đã cấp; không đoán EC2 instance ID. Tham khảo [AWS port forwarding](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html).

Đặt URL với TLS, nhập password ẩn; đoạn này **không in URL/password**. Với tunnel dùng port 15437 và hostaddr loopback nhưng vẫn giữ hostname RDS để verify certificate.

~~~powershell
$rdsHostName = Read-Host 'Endpoint DNS RDS test, ke ca khi dung tunnel'
$rdsDatabaseName = Read-Host 'Database test duoc cap'
$rdsUserName = Read-Host 'DB user duoc cap'
$rdsPortNumber = [int](Read-Host 'Port ket noi: 5432 truc tiep hoac 15437 tunnel')
$rdsCaPath = (Resolve-Path -LiteralPath (Read-Host 'Duong dan CA certificate RDS do nhom cap')).Path
$useLocalTunnel = (Read-Host 'Dung tunnel loopback? y/n') -eq 'y'
$secureDatabasePassword = Read-Host 'DB password (khong hien thi)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureDatabasePassword)
try {
    $encodedDatabasePassword = [Uri]::EscapeDataString([Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer))
    $encodedCaPath = [Uri]::EscapeDataString($rdsCaPath)
    $sslQuery = "sslmode=verify-full&sslrootcert=$($encodedCaPath)&connect_timeout=5"
    if ($useLocalTunnel) { $sslQuery += '&hostaddr=127.0.0.1' }
    $rdsUrl = "postgresql+psycopg2://$([Uri]::EscapeDataString($rdsUserName)):$($encodedDatabasePassword)@$($rdsHostName):$($rdsPortNumber)/$([Uri]::EscapeDataString($rdsDatabaseName))?$($sslQuery)"
    Set-LearnCloudEnvValue -Path (Join-Path $learnCloudRoot '.env') -Key DATABASE_URL -Value $rdsUrl
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    Remove-Variable secureDatabasePassword,passwordPointer,encodedDatabasePassword,rdsUrl -ErrorAction SilentlyContinue
}
~~~

Nạp lại hàm mục 4 nếu mở terminal mới. Không hạ sslmode xuống disable để chữa lỗi certificate. [TLS của RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html), [ý nghĩa host/hostaddr của libpq](https://www.postgresql.org/docs/16/libpq-connect.html).

Restart Uvicorn như mục 8.3. **Không nạp schema.sql/seed.sql hoặc loop migrations vào RDS để thử kết nối.**

### 10.2. S3 và AI Pipeline không chỉ là thêm một biến env

Chỉ nhận bucket/role/queue/model từ AWS owner. Không ghi resource ID thật vào tài liệu này.

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
$backendEnv = Join-Path $learnCloudRoot '.env'
$testVideoBucket = Read-Host 'Ten S3 bucket test da duoc cap'
Set-LearnCloudEnvValue -Path $backendEnv -Key S3_BUCKET -Value $testVideoBucket
Set-LearnCloudEnvValue -Path $backendEnv -Key ALLOW_RAW_VIDEO_PLAYBACK -Value 'false'
~~~

Điều kiện trước khi bật pipeline:

1. Schema ledger/constraints/migration history đã được DB owner kiểm tra.
2. S3 private, browser PUT CORS/headers phù hợp presign; IAM Backend được cấp các operation cần thiết.
3. EventBridge rules/input transformer, Step Functions Standard, pipeline Lambda, MediaConvert role/queue, outbox relay/recovery đã deploy đúng.
4. AI worker/Transcribe/Bedrock thật có tích hợp, IAM/model/region đúng. Code worker nhận completion proof, không coi mọi execution SUCCEEDED là đã sinh học liệu.
5. Dùng [checklist triển khai](../../infrastructure/deployment/deploy-checklist.md) và [hướng dẫn pipeline](../../docs/aws-video-pipeline-console-setup.md); trạng thái thực trên AWS phải do nhóm xác nhận, không suy từ file JSON.

Sau khi các điều kiện được xác nhận, **AWS owner** cung cấp các giá trị cho đoạn cấu hình sau:

~~~powershell
$mediaConvertRoleArn = Read-Host 'MediaConvert role ARN test da duoc duyet'
$mediaConvertQueueArn = Read-Host 'Queue ARN test, de trong neu dung default'
$videoEventBusName = Read-Host 'Event bus name da duoc duyet'
Set-LearnCloudEnvValue -Path $backendEnv -Key MEDIACONVERT_ROLE_ARN -Value $mediaConvertRoleArn
Set-LearnCloudEnvValue -Path $backendEnv -Key MEDIACONVERT_QUEUE_ARN -Value $mediaConvertQueueArn
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_EVENT_BUS -Value $videoEventBusName
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_PROCESSOR_BACKEND -Value 'eventbridge'
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_PIPELINE_ENABLED -Value 'true'
# Khong bat AI tu dong; chi doi true khi AI worker da tich hop va duoc nghiem thu.
Set-LearnCloudEnvValue -Path $backendEnv -Key VIDEO_AI_ENABLED -Value 'false'
~~~

Các flag trong Backend local không tự deploy/cập nhật env Lambda hoặc AWS rules. Adapter MediaConvert hiện ràng buộc Region **ap-southeast-1**; cấu hình khác cần người phụ trách đánh giá source, không tự bỏ guard. Backend mặc định pipeline disabled; local processor chỉ ghi yêu cầu job, **không có worker local tự biến video thành transcript/AI**.

Ở source Step Functions hiện tại, nếu **VIDEO_AI_ENABLED=false**, có thể execution SUCCEEDED nhưng ledger mới VIDEO_READY và Lesson vẫn PROCESSING. Chưa đạt REVIEW_REQUIRED, không có học liệu để duyệt. TUTOR_USE_BEDROCK là flag khác, không tự bật pipeline AI:

~~~powershell
# Chi export trong terminal Backend khi nhom da cap model va cho phep dung Bedrock:
$env:BEDROCK_MODEL_ID = Read-Host 'Bedrock model/inference profile ID duoc cap'
$env:TUTOR_USE_BEDROCK = 'true'
~~~

TUTOR_USE_BEDROCK chỉ ảnh hưởng nhánh tạo Tutor context; send_message hiện trích transcript theo từ khóa, không được khẳng định là chat Bedrock đầy đủ. Không bật flag để che lỗi quota/IAM/schema.

## 11. Sử dụng theo vai trò STUDENT

Screen NN là số ảnh/spec, không phải URL browser. Các URL có :courseId/:lessonId… lấy từ course/lesson đang mở, không gõ ID mẫu tùy ý. Mở /login từ PowerShell:

~~~powershell
Start-Process 'http://127.0.0.1:5173/login'
~~~

| Bước, màn hình | Thao tác và URL UI | API/dịch vụ liên quan | Điều kiện và kết quả thực tế |
|---|---|---|---|
| 1. Đăng ký/xác minh, screen 02–04 | /register → /verify-email → /register-success | POST /auth/register; POST /auth/verify-email; POST /auth/resend-verification → Cognito | Môi trường thật cần email nhận OTP, IAM cho đồng bộ DB; mock làm trong browser như mục 5. Không cho chọn role đặc quyền khi signup. |
| 2. Đăng nhập, screen 01 | /login, nhập account của bạn | Amplify signIn → Cognito; GET /auth/me | JWT Access Token hợp lệ và sub map DB. Mock chỉ STUDENT. Không có backend login local. |
| 3. Khám phá/enroll, screen 07–10 | /courses → mở chi tiết → “Đăng ký” → /my-courses | GET /courses; GET /courses/{course_id}; POST /courses/{course_id}/enroll; GET /students/me/courses | Course PUBLISHED; Student hiện tại. Enroll thật trùng trả 409; mock lưu theo account. Không coi email seed là tài khoản đăng nhập được. |
| 4. Lộ trình/học video, screen 11–13 | Mở course, chọn lesson tại /courses/:courseId/lessons/:lessonId | GET /lessons/{lesson_id}/content; GET /lessons/{lesson_id}/video-url; GET /courses/{course_id}/unlock-status | Enrolled, course/lesson published và section unlocked theo rule sản phẩm. Mock có video /cloud.mp4. Thật cần processed video trên S3; unlock guard Backend còn gap theo kiểm toán. |
| 5. Transcript/summary/concepts | Tab/nội dung trên trang học, bấm mốc transcript để tua | GET /lessons/{lesson_id}/content | Có dữ liệu đúng schema; frontend hiện chỉ giữ concept dạng string, Backend review lưu object term/definition; transcript sinh text-only có thể không có segments, UI trống. Không tự kết luận là AI đã chạy thành công. |
| 6. Flashcards, screen 14–16 | Nút “Flashcard” của lesson; lật, “Đã nhớ/Cần ôn”, ôn lại | GET /lessons/{lesson_id}/flashcards | Thẻ approved/published và enrolled. Rating/remembered hiện lưu browser, chưa có learner-review API/DB qua thiết bị; Student không được PUT/DELETE/approve nội dung. |
| 7. Tiến độ, screen 12/29 | Xem video rồi mở /progress hoặc quay lại lesson | POST /lessons/{lesson_id}/viewing-sessions; PUT /lessons/{lesson_id}/progress; GET /courses/{course_id}/progress; GET /students/me/learning-overview | Mock merge ranges và resume. **Thật còn lỗi 422:** FE gửi playback_session_id/sequence/request_id mà DTO không nhận; Backend chưa lưu ranges/resume và dùng ngưỡng completed 10%. Không hứa tiếp tục xem đúng vị trí trên real mode. |
| 8. Checkpoint, screen 17–22 | /courses/:courseId/sections/:sectionId/checkpoint → Bắt đầu → chọn đáp án → Nộp → Xác nhận | GET /sections/{section_id}/quiz; POST /quizzes/{quiz_id}/attempts; GET /quizzes/{quiz_id}/attempts | Course published/enrolled, quiz approved, đủ completion lesson, checkpoint trước đã pass. Backend chấm; câu bỏ trống sai; UUID request_id giữ nguyên khi retry mạng. Không nộp lại key với đáp án khác. |
| 9. Tutor/practice, screen 23–27 | Từ kết quả bấm Tutor; /tutor/attempts/:attemptId | POST /student/remediation; POST /student/remediation/{id}/advance; POST /student/remediation/{id}/practice; có GET resume | **Cần attempt thật có ID số**, chưa pass và thuộc account. Xem hết giải thích → lật/đánh dấu ôn thẻ → nộp practice. Workflow mới đạt ceil(2N/3), thường 2/3, mở retry đúng attempt. Tutor không có mock adapter cho mock attempt. |
| 10. Mở section/hoàn thành, screen 20/28–29 | Quay lộ trình, mở lesson kế; /courses/:courseId/completed và /progress | unlock-status; GET /courses/{course_id}/completion; /students/me/checkpoint-history | ≥80% checkpoint mở section tiếp; không có API cho client tự unlock. /completion vẫn gọi Backend kể cả VITE_USE_MOCK=true, nên trang completion chưa dùng được với mock token. |

**Ba mức checkpoint:** ≥80% pass/mở section; 50–<80% được retry ngay, Tutor tùy chọn; <50% phải hoàn thành remediation/practice trước retry. Trong mock, nếu rơi <50%, Tutor thật không nhận mock attempt nên luồng chưa khép kín; muốn demo liên tục chọn tình huống pass hoặc tài khoản/course thử mới, không sửa điểm/guard Backend.

Ba API /tutor/sessions, /tutor/sessions/{id}/messages, /tutor/sessions/{id}/practice-attempts vẫn tồn tại trong Swagger, nhưng **không phải luồng TutorPage đang gọi**. Legacy practice yêu cầu đúng tất cả và chưa nối guard retry checkpoint; không trộn hai luồng khi thử.

## 12. Sử dụng theo vai trò INSTRUCTOR

Cần account thật có users.role=INSTRUCTOR, đúng sub và DB schema. Không tự nâng role bằng Cognito group. Sidebar Instructor chỉ xuất hiện sau /auth/me trả role phù hợp.

~~~powershell
Start-Process 'http://127.0.0.1:5173/instructor/dashboard'
~~~

| Bước, màn hình | Thao tác/UI | API đang dùng | Điều kiện và giới hạn |
|---|---|---|---|
| 1. Dashboard/list, screen 30–31 | /instructor/dashboard; /instructor/courses | GET /instructor/dashboard; GET /instructor/courses | Dữ liệu course của mình. Có route trùng, handler runtime khác OpenAPI; chưa đủ bằng chứng dashboard/report E2E. |
| 2. Tạo course, screen 32 | “Tạo khóa học” → /instructor/courses/new; nhập title/mô tả/objectives, cover tùy chọn | POST /courses | Owner lấy từ JWT/DB, course DRAFT. Cover hiện là PNG/JPEG base64 giới hạn 250 KB, không phải quy trình S3 upload cover riêng. |
| 3. Thêm section/lesson, screen 33–34 | /instructor/courses/:courseId/edit → Thêm section → Thêm lesson | GET /instructor/courses/{id}; PATCH /courses/{id}; POST /courses/{id}/sections; POST /sections/{id}/lessons | Chỉ owner; position không trùng trong cùng cha. Trùng lesson position hiện có thể trả 500 thay 409; sửa thứ tự hợp lệ, không xóa DB để né lỗi. |
| 4. Upload, screen 35 | Chọn lesson → /instructor/courses/:courseId/lessons/:lessonId/upload → chọn file → Tải video | POST /lessons/{id}/upload-url; browser PUT trực tiếp presigned S3 URL | MP4/WebM/MOV, >0 và ≤500 MiB theo code; MIME phải khớp. Cần AWS/IAM/S3 CORS; chế độ ledger yêu cầu course/lesson DRAFT. Không truyền byte video qua FastAPI. |
| 5. Theo dõi/retry, screen 36–37 | Cùng trang upload, theo dõi polling; khi FAILED bấm Thử xử lý lại | GET /lessons/{id}/processing-status; POST /lessons/{id}/retry | Poll khoảng 5 giây; retry chỉ FAILED và workflow sẵn sàng. Upload 100% chỉ có nghĩa PUT S3 xong, không phải REVIEW_REQUIRED/AI hoàn tất. Disabled workflow có thể trả 503. |
| 6. Review, screen 38–43 | /instructor/review-queue → mở /instructor/review/:lessonId; xem tab summary/concepts/flashcards/quiz; lưu/duyệt | GET /lessons/{id}/content; GET/PUT /lessons/{id}/review-draft; POST /lessons/{id}/review-draft/approvals | Cần draft REVIEW_REQUIRED + quiz và đúng revision/owner. Backend trả revision mới sau save; conflict 409 thì reload. **UI save hiện không gửi flashcards**, có nguy cơ mất bộ thẻ do default rỗng; chỉ thử dữ liệu bỏ được. Duyệt thật còn thiếu processed-video guard theo audit. |
| 7. Publish course, screen 44 | Trong cấu trúc course bấm Publish và xác nhận | POST /courses/{course_id}/publish | Các section có lesson, lesson được duyệt, nội dung đầy đủ theo rule; code còn thiếu một số guard video/approval. HTTP 200 hiện không đủ chứng minh sẵn sàng phát video; cần thử Student thật trên sandbox. |
| 8. Học viên/thống kê, screen 45–46 | /instructor/student-report → mở chi tiết /instructor/students/:id | GET /instructor/students; GET /instructor/students/{id}; có GET /instructor/courses/{id}/analytics | Chỉ course của mình. Student detail có lỗi progress_percent/HTTP 500; nhiều số liệu tutor/topics còn placeholder. Không diễn giải mọi số 0/— trên UI thành số liệu đã đo. |

Đối với thử AI review **qua Swagger**: có POST /lessons/{id}/review-drafts nhận transcript/num_questions/allow_fallback; chỉ dùng cho lesson test của mình và khi được phép gọi AI. allow_fallback=true cho phép mock adapter khi một số lỗi AWS, **không chứng minh Bedrock thật đã thành công**. Form review hiện không tự tạo transcript/pipeline mới chỉ vì mở trang.

Guard Flashcard đã sửa P0: chỉ INSTRUCTOR owner được POST/PUT/DELETE/approve; ADMIN không có quyền sửa nội dung mọi khóa học. Student vẫn được đọc thẻ đã publish đủ quyền.

## 13. Sử dụng theo vai trò ADMIN

Cần account Admin đã được provision đúng cả Cognito và PostgreSQL. Khi chưa có Admin đầu tiên, nhờ người phụ trách thực hiện quy trình bootstrap đã duyệt; public signup không tạo Admin.

~~~powershell
Start-Process 'http://127.0.0.1:5173/admin/users'
~~~

| Bước, màn hình | Thao tác/UI | API/dịch vụ | Điều kiện và giới hạn |
|---|---|---|---|
| 1. Xem/tìm tài khoản, screen 47 | /admin/users, tìm tên/email | GET /admin/users | ADMIN-only; hiện search, chưa có đủ phân trang/status filter Backend. |
| 2. Tạo Instructor, screen 48/50 | Tạo tài khoản → /admin/users/new → nhập tên/email, role Instructor và password thử theo chính sách → Tạo | POST /admin/users → Cognito admin_create_user + nhóm + DB | Cần IAM Cognito admin và DB. Không chụp màn hình success chứa password. Mặc dù UI ghi “mật khẩu tạm”, Backend hiện đặt Permanent=True và SUPPRESS email; **chưa có luồng invite/bắt đổi lần đầu đúng mô tả UI**. |
| 3. Đổi role, screen 49/51–52 | Mở /admin/users/:userId/edit → chọn role → lưu; /admin/roles để xem bảng quyền | PATCH /admin/users/{id}; bảng roles tĩnh | Role DB là nguồn chính. Không được hạ Admin cuối (409); role=null 422. User bị đổi role nên refresh /auth/me hoặc đăng nhập lại để UI cập nhật; token cũ không phục hồi role Backend. |
| 4. Reset/khóa tài khoản | Màn sửa có nút/checkbox trạng thái | **Chưa có API quản trị hoàn chỉnh tương ứng** | Reset/khóa hiện chỉ thông báo hoặc state UI; không kết luận account đã bị vô hiệu hóa. Public forgot/reset không đồng nghĩa admin reset account. |
| 5. Giám sát, screen 53–54 | /admin/monitoring → chọn job | GET /admin/monitoring/jobs | Có list ledger nhưng UI có fallback DEMO_JOBS, badge dữ liệu minh họa, KPI/log mẫu; chưa có job-log detail/CloudWatch/cost hoàn chỉnh. Không dùng các tỷ lệ minh họa để báo cáo vận hành thật. |

Admin không mặc định là Instructor hoặc Student. Không dùng tài khoản Admin để thử sửa Flashcard hay enroll/học như Student; dùng đúng tài khoản test từng vai trò và course ownership.

## 14. Kiểm tra nhanh và bằng chứng đã có

### 14.1. Frontend

~~~powershell
Set-Location -LiteralPath (Join-Path $learnCloudRoot 'frontend')
npm.cmd test
# Neu muon kiem build tren may cua ban:
npm.cmd run build
~~~

Trong lượt viết hướng dẫn: **npm test 46/46 đạt**. Không chạy browser test hoặc build/deploy trong lượt này. Unit tests frontend không chứng minh Cognito/Backend/RDS thực đã tích hợp.

### 14.2. Backend P0 — test offline an toàn

Tại root, cài pytest cho môi trường phát triển nếu chưa có; runtime requirements chưa chứa nó:

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
.\.venv\Scripts\python.exe -m pip install pytest
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
@'
import os, runpy, socket, sys
from contextlib import ExitStack
from unittest.mock import patch
sys.path.insert(0, "backend")
offline = runpy.run_path("backend/tests/run_unit_offline.py")
os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
os.environ.update({
    "COGNITO_USER_POOL_ID": "ap-southeast-1_testpool",
    "COGNITO_APP_CLIENT_ID": "test-client",
    "LEARNCLOUD_RUN_PIPELINE_DB_TESTS": "0",
})
import pytest
with ExitStack() as stack:
    for obj, name, replacement in [
        (socket.socket, "connect", offline["deny_network"]),
        (socket.socket, "connect_ex", offline["deny_network"]),
        (socket.socket, "sendto", offline["deny_network"]),
        (socket, "getaddrinfo", offline["deny_network"]),
        (socket, "create_connection", offline["deny_network"]),
        (socket, "socketpair", offline["internal_socketpair"]),
    ]:
        stack.enter_context(patch.object(obj, name, replacement))
    raise SystemExit(pytest.main([
        "backend/tests/unit/test_authorization_p0.py",
        "backend/tests/unit/test_auth_integration.py",
        "-q", "-p", "no:cacheprovider",
    ]))
'@ | .\.venv\Scripts\python.exe -X utf8 -
~~~

Hai ID Cognito trong test là **giá trị giả trong process**, không phải cấu hình AWS để đăng nhập. Không chạy riêng pytest với .env đang trỏ RDS rồi đoán conftest sẽ tự đổi DB: conftest chỉ setdefault DATABASE_URL.

Bằng chứng cần phân biệt:

| Kiểm tra | Mức bằng chứng |
|---|---|
| Lượt này: ASGI offline /health 200, /openapi.json 200, 68 operations/56 paths, ba Tutor POST có; /auth/me thiếu token 401 | **ĐÃ CHẠY**, không nối DB mạng/AWS. |
| Lượt này: npm test 46 đạt | **ĐÃ CHẠY** unit/mock tests; không phải browser E2E. |
| Bản sửa P0 trước đó: 98 test liên quan đạt; full backend 176 đạt/75 lỗi cũ | **ĐÃ KIỂM CHỨNG TRONG BÁO CÁO P0**, không coi toàn bộ suite đã xanh. |
| Vite dev/browser, PostgreSQL Docker/schema bootstrap, đăng nhập Cognito/email/S3/RDS/pipeline thật trên máy thành viên | **UNVERIFIED trong lượt hướng dẫn này**; làm theo từng bước và ghi kết quả thực của máy bạn. |
| Logic màn/API chưa có test tương ứng hoặc AWS deployment chỉ có file source | **PHÂN TÍCH TĨNH**, không đánh dấu hoàn thiện. |

## 15. Xử lý lỗi thường gặp

### 15.1. Thiếu Python package / sai virtual environment

Chạy từ root, dùng đúng interpreter:

~~~powershell
.\.venv\Scripts\python.exe -m pip --version
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy, psycopg2, boto3, jwt, mangum; print('Backend imports OK')"
~~~

Không chữa ModuleNotFoundError bằng cài package vào Python khác. app/ai_pipeline không tìm thấy: dùng lệnh Uvicorn từ root với --app-dir backend. Nếu PyJWT/crypto lỗi, cài lại cả requirements, không cài package tên jwt thay PyJWT.

### 15.2. Thiếu aws-amplify / Vite / Node không phù hợp

~~~powershell
Set-Location -LiteralPath (Join-Path $learnCloudRoot 'frontend')
node --version
npm.cmd ci
npm.cmd ls aws-amplify vite react --depth=0
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
~~~

aws-amplify đã khai báo trong package.json/lock. Nếu PowerShell chặn npm.ps1, dùng npm.cmd. Nếu ERESOLVE/engine mismatch, kiểm Node engines và lockfile, không thêm --force/--legacy-peer-deps hoặc xóa lock để làm mất bằng chứng.

### 15.3. Cognito chưa cấu hình / login 401, 409, 503

- Chưa AWS: dùng cả hai mock=true và đăng ký Student mock; VITE_USE_MOCK=true một mình không mock login.
- Thật: kiểm file frontend/.env và root .env có cùng pool/client/region; restart cả hai process.
- Client có secret hoặc thiếu USER_PASSWORD_AUTH: kiểm bằng lệnh đọc mục 8.2, nhờ AWS owner điều chỉnh.
- Cognito login thành công nhưng /auth/me 401: kiểm sub mapping DB, account đã verify/provision; role group không thay DB role.
- Login yêu cầu MFA/password challenge chưa hỗ trợ: UI báo 409; không tắt xác thực Backend để vượt.
- AWS credentials/IAM của Backend khác session Cognito browser; cần profile đúng cho admin_get_user/provision/S3.

### 15.4. Backend không kết nối PostgreSQL local

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
docker compose ps
docker exec learncloud-db pg_isready -U learncloud -d learncloud
Test-NetConnection -ComputerName 127.0.0.1 -Port 5434
docker compose logs --tail 50 learncloud-db
~~~

Kiểm DATABASE_URL chỉ còn một dòng, port host 5434, user/database đúng Compose. Không in URL chứa password. Authentication failed có thể do volume cũ dùng password khác. Missing column/table là lỗi schema ở mục 7.3, không phải chỉ restart Uvicorn là hết.

### 15.5. RDS timeout / certificate

~~~powershell
# Chi dung host RDS test da duoc phep:
Test-NetConnection -ComputerName $rdsHostName -Port 5432
# Neu dung tunnel, kiem port local:
Test-NetConnection -ComputerName 127.0.0.1 -Port 15437
~~~

Timeout: kiểm VPN/tunnel còn mở, bastion/SG/subnet/routing do AWS owner cấp. Không mở 5432 cho Internet để chữa nhanh. SSL lỗi: kiểm CA, host DNS RDS, hostaddr khi tunnel và URL encoding; không tắt TLS. Không thử schema/migration/seed trên RDS để kiểm kết nối.

### 15.6. Swagger không cập nhật

~~~powershell
$apiSchemaNow = Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json'
$apiSchemaNow.info | Select-Object title,version
$apiSchemaNow.paths.PSObject.Properties.Name | Where-Object { $_ -like '/tutor/*' }
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
~~~

Xem đúng process/terminal, Ctrl+C rồi chạy lại đúng app.main:app --app-dir backend; refresh /docs bằng Ctrl+F5. Đối chiếu /openapi.json trước khi đổ lỗi cache. Endpoint có nhưng handler/shape khác Swagger có thể là 5 route trùng đã nêu trong audit; không tự tạo endpoint mới.

### 15.7. Frontend gọi API thất bại

| Hiện tượng | Kiểm tra/giải thích |
|---|---|
| Failed to fetch / connection refused | Backend đã chạy đúng 8000? URL API không có /docs? Network tab chỉ host nào? |
| URL cũ dù sửa VITE_API_URL | VITE_API_BASE_URL có ưu tiên cao hơn; .env.local/mode hoặc env process ghi đè. Restart Vite, build lại nếu preview. |
| CORS | Dùng 5173 và origin localhost/127.0.0.1 được phép. 5174/4173 không nằm trong allow_origins hiện tại. |
| “Tài khoản mô phỏng không thể gọi API thật” | Auth mock token đi vào adapter real. Không vá client để gửi token đó; chuyển đúng chế độ hoặc dùng chức năng mock đã hỗ trợ. |
| 401 | Thiếu/sai/hết hạn token, không map sub hoặc cấu hình Cognito khác nhau. |
| 403 | Role/owner/enrollment/published/unlock hoặc completion lesson chưa đạt. Không nâng role bằng header. |
| PUT progress 422 | Payload FE session/sequence/request_id chưa khớp Backend DTO; lỗi triển khai đã biết, không có bước cấu hình chữa được. |
| Checkpoint bị khóa dù đã xem video | Progress thật có thể chưa lưu được vì 422; hoặc chưa pass section trước/đang nợ remediation. |
| Tutor mock không chạy | Mock attempt không có ID số thật; TutorPage chỉ có real adapter. |
| Review mất flashcard sau save | FE PUT nháp hiện không gửi flashcards; PATCH ai-content cũng có lỗi whitelist/merge đã audit. Dừng thử trên dữ liệu quan trọng, báo Backend/Frontend owner. |
| Transcript/concepts trống | Kiểm schema content/segments và string vs object concepts, không suy AI đã hoàn thiện. |
| Student detail 500 hoặc monitoring có số liệu đẹp khi API lỗi | Read model detail còn lỗi; monitoring có fallback/minh họa. Không coi đó là số liệu thật. |

Chỉ xem tên file env đang tồn tại, không dump nội dung:

~~~powershell
Get-ChildItem -LiteralPath (Join-Path $learnCloudRoot 'frontend') -Force -Filter '.env*' |
    Select-Object Name
~~~

Khi báo lỗi cho nhóm, gửi action, URL path không query nhạy cảm, HTTP status, code/request_id và thông báo đã làm sạch; không gửi Authorization header, password, AWS key, presigned URL hoặc bản .env.

## 16. Dừng và tiếp tục làm việc

- Backend/Vite: Ctrl+C ở đúng terminal.
- Docker local: lệnh sau giữ volume, không reset dữ liệu.

~~~powershell
Set-Location -LiteralPath $learnCloudRoot
docker compose stop learncloud-db
# Lan sau:
docker compose start learncloud-db
~~~

Không dùng down -v như một bước chạy thường ngày. Đổi từ RDS về local: dừng Backend, thực hiện lại mục 7.2 để ghi đúng một DATABASE_URL local, sau đó restart.

## 17. Nguồn source và tài liệu bàn giao

| Nhóm | Nguồn đã đối chiếu |
|---|---|
| Cài/chạy/cấu hình | README.md; backend/requirements.txt; frontend/package.json/package-lock.json; docker-compose.yml; .env.example; frontend/.env.example; backend/app/config.py, database.py, main.py. |
| Auth thật/mock và role | frontend/src/api/auth.api.js, cognito.js, client.js; context/AuthContext.jsx; mocks/account.mock.js; backend/app/dependencies.py, services/auth_service.py, api/admin.py, api/flashcards.py. |
| Route UI và workflow | frontend/src/routes/AppRoutes.jsx; pages/TutorPage.jsx, CourseCompletePage.jsx, LessonReviewPage.jsx, AdminUsersPage.jsx, AdminMonitoringPage.jsx; các frontend/src/api/*.js. |
| Dữ liệu/schema/pipeline | database/schema.sql, migrations/*.sql; backend/app/services/progress/quiz/remediation/review/video_pipeline; infrastructure/step-functions/README.md; deployment/deploy-checklist.md. |
| Trạng thái kiểm chứng | [Kiểm toán API](API_CONTRACT_IMPLEMENTATION_AUDIT.md); [Sửa Authorization P0](AUTHORIZATION_P0_FIX.md). Các P0 role/Flashcard/last-admin đã có bản sửa, nhưng các gap progress/review/publish/report khác không tự trở thành DONE. |

File hướng dẫn không chứa tài khoản/password/token/endpoint AWS thật. Các giá trị môi trường riêng phải lấy từ nhóm theo môi trường được phép; các câu lệnh nhập giá trị có chủ ý không thể thay bằng credentials suy đoán.

