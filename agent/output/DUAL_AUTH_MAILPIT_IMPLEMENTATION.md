# LearnCloud — Dual Auth và Mailpit

Ngày thực hiện: 10/11/2026. Không thao tác AWS hoặc RDS production.

## 1. Kết quả và phân tích source ban đầu

Source ban đầu chỉ cho phép auth mock khi `VITE_USE_MOCK=true`; tài khoản mock dùng localStorage và token `mock:`. API client chỉ lấy token từ Amplify cho phiên thật. Backend đã có Cognito JWT RS256, ánh xạ `cognito_sub`, bảng `users`, các schema tài khoản và Authorization P0 đọc role từ PostgreSQL. Các trang tài khoản đã dùng chung `auth.api.js`, nên tái sử dụng trang và schema hiện tại.

Có hai điểm cần xử lý ngoài việc thêm local login:

- Luồng Cognito còn có thể liên kết bản ghi chưa có `cognito_sub` bằng email, và confirm-signup có thể ghi lại identity. Đã chặn các trường hợp khác subject, kể cả tài khoản local/legacy chưa có subject.
- `database.py` từng tự ghép URL/đọc SSM khi chạy Lambda. Nay mọi môi trường đều lấy `settings.DATABASE_URL`; không gọi AWS khi import database. Deployment Lambda cũ cần được nhóm bổ sung `DATABASE_URL` trước khi triển khai code mới.

Hành vi sau sửa:

| Frontend | Kết quả |
|---|---|
| `VITE_USE_MOCK=false`, `VITE_USE_AUTH_MOCK=true` | Auth nội bộ FastAPI/PostgreSQL, OTP qua SMTP Mailpit, dữ liệu nghiệp vụ từ API thật |
| `VITE_USE_MOCK=false`, `VITE_USE_AUTH_MOCK=false` | Amplify/Cognito như trước, dữ liệu nghiệp vụ từ cùng Backend/PostgreSQL |

Backend hỗ trợ đồng thời cả hai phương thức khi được cấu hình một lần. Frontend chọn nhóm API; không cần đổi cờ Backend mỗi lần chuyển. `VITE_USE_AUTH_MOCK` là tên cờ tương thích cũ, không còn có nghĩa là tạo tài khoản mô phỏng. Không gọi `accountMock` trong luồng xác thực. Phiên thật lưu token trong sessionStorage, kèm nhà cung cấp; chuyển chế độ không khôi phục nhầm phiên của chế độ khác. Token `mock:` bị từ chối.

`frontend/.env` hiện có đã được đổi `VITE_USE_MOCK=false`, giữ lựa chọn local auth đang có. Không đổi URL database hay các secret trong `.env` Backend hiện hữu. Sau khi Backend được cấu hình theo phần 5, chỉ đổi cờ Frontend và restart Vite.

## 2. Những file đã sửa/thêm

| File | Thay đổi |
|---|---|
| `.env.example` | Cấu hình local auth, SMTP, Cognito; một `DATABASE_URL` hoạt động, ví dụ RDS được comment |
| `docker-compose.yml` | Mailpit v1.27.10, bind SMTP/UI vào loopback |
| `backend/requirements.txt` | Thêm argon2-cffi |
| `backend/app/config.py` | Cờ Backend, secret/issuer/audience, TTL, cooldown, giới hạn thử, SMTP |
| `backend/app/database.py` | Dùng duy nhất DATABASE_URL, ẩn SQL parameters trong lỗi |
| `backend/app/models/local_auth.py` | Metadata xác minh email, OTP, session thu hồi được |
| `backend/app/services/local_auth_service.py` | Đăng ký, email, verify/resend, login/logout, recovery, đổi mật khẩu, JWT |
| `backend/app/api/local_auth.py` | Router riêng, gate môi trường, chuyển lỗi sang HTTP |
| `backend/app/schemas/auth.py` | Schema login cấm field ngoài hợp đồng |
| `backend/app/services/auth_service.py` | Chọn verifier local/Cognito; chặn nhận nhầm identity qua email |
| `backend/app/api/admin.py` | Quản lý name/role local không gọi Cognito; chặn đổi email local chưa có luồng xác minh quyền sở hữu mới |
| `backend/app/utils/errors.py` | Không echo input mật khẩu/OTP trong lỗi validation của `/auth/*` |
| `backend/app/main.py` | Đăng ký router local |
| `database/migrations/0007_dual_auth.sql` | Migration bổ sung, không sửa migration cũ hoặc backfill tài khoản |
| `frontend/.env.example` | Mặc định dữ liệu thật, giải thích công tắc auth |
| `frontend/.env` — file ignored hiện có | Đổi `VITE_USE_MOCK=false`; không đưa secret vào Git |
| `frontend/src/config/auth.js` | Chọn nhà cung cấp xác thực |
| `frontend/src/api/auth.api.js` | Route các thao tác tài khoản tới đúng nhà cung cấp |
| `frontend/src/api/client.js` | Dùng JWT Backend cho local, Amplify cho Cognito |
| `frontend/src/api/cognito.js` | Không khởi tạo/sử dụng SDK trong chế độ local |
| `frontend/src/api/session.js` | Phân biệt provider, loại phiên cũ/token mock |
| `frontend/src/context/AuthContext.jsx` | Khôi phục, hết hạn và đăng xuất phù hợp mỗi provider |
| `frontend/src/pages/LoginPage.jsx` | Thông báo local auth/Mailpit và lỗi đúng provider, giữ bố cục |
| `frontend/tests/auth.test.cjs` | Test chọn API, token, phiên, không dùng mock/Cognito trong local mode |
| `frontend/tests/dual-auth-browser.cjs` | Test trình duyệt với Backend/PostgreSQL/Mailpit thật, không có Cognito ID |
| `frontend/package.json` | Lệnh `test:auth-browser` |
| `backend/tests/unit/test_dual_auth.py` | Test dịch vụ, HTTP, JWT, role và chế độ PostgreSQL/Mailpit thật |
| `backend/tests/run_auth_offline.py` | Chạy test auth/P0 với settings giả và chặn socket bên ngoài |
| `agent/output/DUAL_AUTH_MAILPIT_IMPLEMENTATION.md` | Báo cáo duy nhất được tạo trong công việc này |

Register, Verify Email, Forgot/Reset Password, Resend Code và Profile tiếp tục dùng các component hiện có trong `AccountPages.jsx`; thay đổi qua lớp API dùng chung, không sao chép UI.

## 3. API mới và API dùng chung

| Method/path | Payload/chức năng |
|---|---|
| `POST /auth/local/register` | `{name,email,password}`; chỉ STUDENT; trả `verification_required`, `retry_after`, message |
| `POST /auth/local/verify-email` | `{email,code}` |
| `POST /auth/local/resend-verification` | `{email}`; thay OTP cũ sau cooldown |
| `POST /auth/local/login` | `{email,password}`; trả `access_token`, `token_type`, `expires_in` |
| `POST /auth/local/logout` | Bearer local JWT; thu hồi session hiện tại ở PostgreSQL |
| `POST /auth/local/forgot-password` | `{email}`; phản hồi trung lập cho email không phù hợp |
| `POST /auth/local/reset-password` | `{email,code,password}`; thu hồi toàn bộ session của tài khoản |
| `POST /auth/local/change-password` | Bearer local JWT và `{current_password,new_password}`; thu hồi session và mã reset đang tồn tại |

`GET/PATCH /auth/me` dùng chung, tiếp tục trả profile/role từ database. Các API nghiệp vụ giữ nguyên guard. Các endpoint Cognito `/auth/register`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password` giữ luồng Cognito. Cognito login/logout vẫn qua Amplify; không khôi phục proxy `/auth/login`.

Các điều kiện bảo mật đã triển khai:

- Mật khẩu dùng Argon2id, salt ngẫu nhiên; lưu trong `users.password_hash`.
- OTP ngẫu nhiên 6 chữ số, lưu HMAC-SHA256 với nonce và secret phía server, ràng buộc user/purpose. Verify và reset dùng mã riêng. Mặc định hết hạn 600 giây, tối đa 5 lần sai, chờ resend 60 giây. Resend thành công thay hash, mã cũ hết hiệu lực. Không trả/log OTP; email là nơi nhận mã rõ.
- PostgreSQL khóa dòng user để tuần tự hóa resend, consume, login và thu hồi phiên. SMTP lỗi thì rollback thay đổi; mã cũ còn hiệu lực nếu gửi lại thất bại. SMTP được gửi trong transaction; trường hợp email đã nhận nhưng commit DB thất bại có thể cần gửi lại mã.
- Local JWT chỉ nhận HS256 với secret riêng, issuer/audience riêng; bắt buộc `sub,jti,iat,exp,iss,aud`, `token_use=access`, `auth_provider=local`, và session còn hiệu lực trong DB. Không có role tin cậy từ JWT. Mặc định token hết hạn 60 phút; local không có refresh token, cần đăng nhập lại.
- Cognito giữ RS256/JWKS, issuer, client ID và access-token checks. Header chưa xác minh chỉ chọn verifier; mỗi verifier tự xác minh đầy đủ, không fallback sau lỗi.
- Mỗi request bảo vệ đọc lại role hiện tại; không nhận `X-Demo-User`, không cho profile/public signup khai báo role. Admin có thể thu hồi role local bằng API quản trị hiện có mà không gọi AWS.
- Không tự liên kết theo email. Cùng email giữa hai provider bị chặn 409/401 theo thao tác; cần email khác cho hai tài khoản độc lập. Tài khoản legacy có password hash nhưng không có metadata local cũng không được tự động đăng nhập local.
- Local endpoint trả 503 khi cờ tắt, môi trường không phải chính xác `development`/`test`, hoặc secret chưa hợp lệ. Local JWT cũng bị từ chối ở các trạng thái này; Cognito tiếp tục hoạt động.

## 4. Database và migration

Migration mới `0007_dual_auth.sql` chỉ thêm:

- `local_auth_identities`: user_id, verified_at, số lần sai login và thời điểm khóa tạm.
- `local_auth_otps`: user_id/purpose, hash, nonce, sent_at/expires_at, attempts, consumed_at.
- `local_auth_sessions`: hash jti, user_id, expires_at, revoked_at và index.

Có transaction, foreign key và bản ghi version trong `schema_migrations`. Đã áp dụng và chạy lại migration thành công trên cluster PostgreSQL kiểm thử riêng. Không có ALTER/UPDATE liên kết lại users, không thay role hay password của user cũ. Không có migration tự chạy khi Backend khởi động.

Với database hiện hữu, nhóm cần kiểm tra migrations/schema trước đó đã phù hợp code, bao gồm `password_hash` nullable và `0006_screen_workflows.sql`, rồi review/phê duyệt `0007`. Không chạy toàn bộ thư mục migrations theo wildcard vì repository có nhiều file lịch sử cùng tiền tố `0004`. Không dùng bootstrap schema trên DB hiện hữu.

RDS development/test dùng cùng nghiệp vụ thông qua `DATABASE_URL`, kèm TLS và thông tin kết nối do nhóm cấp. Production giữ `APP_ENV=production`, `LOCAL_AUTH_ENABLED=false`. Chưa chạy bất kỳ migration/DML hay tạo dữ liệu thử nào trên RDS; nhóm tự lập kế hoạch backup, review và chạy migration đã phê duyệt.

## 5. Cấu hình một lần và chạy trên Windows 11

Cần Python 3.12, Node/npm, Docker Desktop đang chạy với Linux containers. Chạy PowerShell tại thư mục gốc repository. Dùng `.env` ở **gốc repository** cho Backend; `backend/.env` không phải file mà Settings hiện tại tự đọc.

### Backend `.env`

Ví dụ local development; tạo secret bằng Python rồi lưu vào `.env` riêng:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```dotenv
DATABASE_URL=postgresql+psycopg2://learncloud:learncloud_dev_password@localhost:5434/learncloud
APP_ENV=development
LOCAL_AUTH_ENABLED=true
LOCAL_AUTH_JWT_SECRET=<secret-ngau-nhien-vua-tao-it-nhat-32-byte>
LOCAL_AUTH_JWT_ISSUER=learncloud-local
LOCAL_AUTH_JWT_AUDIENCE=learncloud-api
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
LOCAL_AUTH_OTP_TTL_SECONDS=600
LOCAL_AUTH_RESEND_SECONDS=60
LOCAL_AUTH_OTP_MAX_ATTEMPTS=5
LOCAL_AUTH_LOGIN_MAX_ATTEMPTS=5
LOCAL_AUTH_LOGIN_LOCK_SECONDS=300
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=LearnCloud <no-reply@learncloud.test>
COGNITO_REGION=ap-southeast-1
COGNITO_USER_POOL_ID=<pool-hien-co-neu-can-Cognito>
COGNITO_APP_CLIENT_ID=<client-hien-co-neu-can-Cognito>
```

Không cần hai Cognito ID nếu chỉ dùng local. Muốn chuyển qua lại chỉ bằng Frontend, điền Cognito thật một lần cùng lúc bật local Backend. `JWT_SECRET_KEY` cũ không được dùng để xác minh local JWT mới; phải đặt `LOCAL_AUTH_JWT_SECRET` riêng. Thay secret sẽ làm token/OTP cũ không dùng được.

### PostgreSQL và Mailpit

```powershell
docker compose up -d learncloud-db mailpit
docker compose ps
```

SMTP `localhost:1025`; Web UI [Mailpit](http://localhost:8025). Nếu Backend được tự đóng container trong cùng compose network, đặt SMTP_HOST=mailpit và dùng hostname/port nội bộ của PostgreSQL trong DATABASE_URL.

**Chỉ đối với database local mới, trống** — ví dụ bootstrap cho luồng auth/course đã kiểm thử:

```powershell
Get-Content -Raw -Encoding UTF8 database/schema.sql | docker compose exec -T learncloud-db psql -U learncloud -d learncloud -v ON_ERROR_STOP=1
Get-Content -Raw -Encoding UTF8 database/migrations/0006_screen_workflows.sql | docker compose exec -T learncloud-db psql -U learncloud -d learncloud -v ON_ERROR_STOP=1
Get-Content -Raw -Encoding UTF8 database/migrations/0007_dual_auth.sql | docker compose exec -T learncloud-db psql -U learncloud -d learncloud -v ON_ERROR_STOP=1
```

Các workflow video/AI khác vẫn cần các migration/cấu hình hiện hữu tương ứng của dự án. Với database local hiện hữu đã cập nhật, chỉ áp dụng migration bổ sung đã review, không bootstrap hoặc seed lại. Các lệnh này không nhắm tới RDS.

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Nếu đã có `.venv` thì tái sử dụng. API docs: `http://localhost:8000/docs`.

### Frontend — PowerShell khác

Trong `frontend/.env`:

```dotenv
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK=false
VITE_USE_AUTH_MOCK=true
```

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Mở `http://localhost:5173/register`, tạo Student với email chưa dùng, mở Mailpit và đọc email “LearnCloud - Verify email”, nhập OTP vào trang xác minh rồi đăng nhập. Không có tài khoản/mã cố định. Resend Code khả dụng sau cooldown; đọc email mới nhất, mã cũ không còn hợp lệ. Forgot Password gửi email “Reset password” qua cùng Mailpit.

### Bật/tắt Cognito trên Frontend

- Local: `VITE_USE_AUTH_MOCK=true`; các Cognito ID Frontend có thể để trống.
- Cognito: `VITE_USE_AUTH_MOCK=false`; cấu hình `VITE_AWS_REGION`/`VITE_COGNITO_REGION`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_APP_CLIENT_ID` khớp Backend. Giữ App Client/auth flow đang hoạt động.
- Cả hai luôn giữ `VITE_USE_MOCK=false`. Dừng Vite bằng Ctrl+C rồi chạy lại sau khi sửa cờ; bản build tĩnh cần build lại.
- Chọn tài khoản của đúng provider; hệ thống không tự nhập tài khoản local vào User Pool hay liên kết email trùng. Tắt local hoàn toàn bằng cờ Backend `LOCAL_AUTH_ENABLED=false` và restart Backend.

## 6. Kết quả kiểm thử trước/sau

Mọi test dùng settings kiểm thử riêng. Không lấy URL database trong `.env` làm test target. Test offline chặn socket và credentials AWS; test PostgreSQL chỉ chấp nhận DB/user `learncloud_auth_test` tại loopback và cấm query override host.

| Kiểm tra | Trước sửa | Sau sửa |
|---|---|---|
| Frontend `npm.cmd test` | 46 pass | 52 pass |
| Auth/Cognito/Authorization P0 offline | 46 pass | 81 pass, gồm 35 ca dual auth mới |
| Dual auth với PostgreSQL và SMTP Mailpit thật | Chưa có | 35 pass |
| Trình duyệt thật, không có Cognito ID, không dùng mock | Chưa có | Pass: register → Mailpit → verify → login → profile → logout → forgot/reset → login; Student bị chặn trang Admin |
| Build với auth local và dữ liệu thật | Luồng bị chặn theo source cũ | Pass, Cognito ID để trống |
| Build với auth Cognito và dữ liệu thật | Không chạy build baseline | Pass |
| Toàn bộ Backend unit suite, so với snapshot Git HEAD trước sửa | 176 pass, 75 fail, 6 subtests pass | 211 pass, cùng 75 fail, 6 subtests pass |
| Migration 0007 trên PostgreSQL kiểm thử | Chưa có | Apply và chạy lại thành công |
| `docker compose config --quiet` và `git diff --check` | Không chạy baseline | Pass |

75 test lỗi của suite rộng là các test cũ đã lỗi ở baseline; đã đối chiếu danh tính các ca lỗi, không có lỗi mới. Nhiều test vẫn dùng danh tính demo hoặc mock các thành phần workflow đã thay đổi nên nhận 401/lỗi fixture. Không sửa guard để các test này pass. Build còn warning của react-router về `use client` và chunk lớn; không có build error.

Ma trận dual auth bao gồm đăng ký Student/hash mật khẩu; gửi SMTP; resend/cooldown/mã cũ; hết hạn và giới hạn sai; verify một lần; nhiều session và logout; JWT sai chữ ký/unsigned/thiếu claim/hết hạn/sai issuer/audience/session; khóa thử login; reset/change thu hồi phiên; role lấy lại từ DB; Admin sửa/thu hồi role local; tắt local trong production; Cognito RS256 vẫn hoạt động; hai tài khoản khác provider cùng enroll một khóa học thật; chặn chiếm tài khoản theo email theo cả access-token/authorizer và confirm-signup.

Môi trường thực thi: PostgreSQL 18 native trên cluster mới trong thư mục tạm, `127.0.0.1:55439`, DB/user `learncloud_auth_test`; Mailpit v1.27.10 native, SMTP `127.0.0.1:11025`, HTTP `127.0.0.1:18025`. Không sửa PostgreSQL service/database có sẵn trên máy. Docker daemon không chạy, nên xác minh dịch vụ thật bằng native executables thay vì khẳng định đã chạy Docker Compose.

Các dịch vụ native tạm dùng cho kiểm thử đã được dừng sau khi xác minh; chúng không phải dịch vụ development của nhóm. Muốn chạy lại test tích hợp cần khởi động lại môi trường test riêng.

Test HTTP dùng outer transaction/savepoint và rollback dữ liệu từng ca. Test trình duyệt tạo tài khoản ngẫu nhiên, commit thật **chỉ trong DB kiểm thử riêng**. Các test cũng chạy thành công khi DB kiểm thử đã có tài khoản từ lần chạy trình duyệt trước.

Chạy lại test offline:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe backend/tests/run_auth_offline.py
Set-Location frontend
npm.cmd test
```

Chạy PostgreSQL/Mailpit test sau khi nhóm chuẩn bị database riêng đúng tên/user, schema và migration 0007; mở Mailpit riêng tại các port test nêu trên:

```powershell
# Tại repository root; không dùng DATABASE_URL development/RDS làm target test.
$env:DATABASE_URL='sqlite:///:memory:'
$env:AWS_EC2_METADATA_DISABLED='true'
$env:PYTHONPATH='backend'
$env:LEARNCLOUD_RUN_AUTH_DB_TESTS='1'
$env:LEARNCLOUD_AUTH_TEST_DATABASE_URL='postgresql+psycopg2://learncloud_auth_test@127.0.0.1:55439/learncloud_auth_test'
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_dual_auth.py -q -p no:cacheprovider

# Chrome/Edge, .venv và port 5173 trống; tự chạy Backend/Vite cô lập.
Set-Location frontend
npm.cmd run test:auth-browser
```

Các env test được đặt trong PowerShell kiểm thử riêng; đóng terminal này sau khi chạy để không dùng nhầm settings test cho quá trình development.

## 7. Những phần chưa được kiểm chứng và giới hạn

- Không gọi AWS thật: chưa thực hiện login, signup/email delivery, refresh, MFA hay quản trị user trên Cognito production. Cognito được kiểm thử bằng JWT RSA ký thật trong test; chỉ JWKS/administrative responses được thay bằng fixture. Không thay đổi cơ chế email của Cognito.
- Chưa kết nối Amazon RDS, chưa kiểm thử TLS/network/permissions trên RDS hoặc deploy Lambda. Chưa xác nhận các cấu hình infrastructure production hiện có.
- Chưa chạy Docker Compose thực tế vì daemon tắt; image tag đã kiểm tra với release chính thức. SMTP/Web UI native Mailpit đã hoạt động trong test.
- Trình duyệt đã kiểm thử chế độ local với dữ liệu thật. Chuyển provider và route Cognito được kiểm thử ở lớp API/session/SDK bằng test tự động; chưa đăng nhập Cognito thật qua browser. Chưa click UI Resend sau đủ 60 giây trong browser; API resend/cooldown/OTP cũ đã kiểm thử với Mailpit thật.
- Script demo lịch sử `npm run test:browser` dùng mock business/accounts và OTP cố định không được dùng để xác nhận luồng mới. Dùng `npm run test:auth-browser` cho auth thật. Các unit test fixture mock nghiệp vụ vẫn độc lập với cấu hình ứng dụng.
- Không tự liên kết/import legacy user; đổi email local cần luồng xác minh quyền sở hữu riêng, hiện trả 409 khi Admin yêu cầu đổi địa chỉ. Không có local refresh-token/MFA. Không load-test SMTP hoặc xác minh đa process/concurrency bằng stress test; việc tuần tự hóa dùng PostgreSQL row lock.
- Nếu đi qua API Gateway chỉ nhận JWT Cognito, gateway có thể từ chối JWT local trước khi tới FastAPI. Luồng development đã kiểm tra gọi trực tiếp FastAPI. Triển khai dual auth phía sau gateway cần nhóm review routing/authorizer riêng; không tắt/bỏ guard Backend và không chỉnh AWS trong công việc này.
- Không xác nhận toàn bộ video/AI/storage workflow bằng end-to-end; các lỗi unit cũ đã được nêu rõ thay vì hạ bảo vệ để đạt số pass.

Tài liệu chính thức đối chiếu: [argon2-cffi PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/api.html), [PyJWT: issuer/audience/required claims](https://pyjwt.readthedocs.io/en/stable/usage.html), [Mailpit v1.27.10](https://github.com/axllent/mailpit/releases/tag/v1.27.10).
