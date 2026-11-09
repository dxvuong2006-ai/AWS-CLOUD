# Phan tich cau hinh quyen mat khau va xac thuc

Ngay: 2026-11-07

## 1. Muc tieu

Danh gia nen dung Amazon Cognito hay mot luong quyen mat khau rieng cho LearnCloud va de xuat kien truc phu hop voi implementation hien tai.

## 2. Tai lieu va source da kiem tra

- `backend/app/api/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/schemas/auth.py`
- `backend/scripts/set_user_password.py`
- `frontend/src/api/auth.api.js`
- `frontend/src/pages/LoginPage.jsx`
- `agent/output/AUTH_CONFLICT_ANALYSIS.md`
- `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md`

## 3. Ket luan

LearnCloud hien dang dung:

- Password hash Argon2id trong PostgreSQL.
- Access token JWT HS256 do FastAPI sinh va xac minh.
- Phan quyen doc role tu bang User trong database.
- Frontend goi `/auth/login`, `/auth/me`, `/auth/change-password`.

Trang Forgot Password da co o frontend va cac ham frontend da khai bao `forgotPassword`/`resetPassword`, nhung backend hien chua co endpoint `/auth/forgot-password` hoac `/auth/reset-password`, cung chua co luong email reset.

Amazon Cognito chua co bang chung ton tai trong inventory Singapore/Sydney da kiem ke.

## 4. De xuat kien truc

### Lua chon A - Kien truc hien tai: backend JWT + PostgreSQL + SES

Dung cho giai doan hien tai neu muon day nhanh va khong muon migration auth lon.

- Backend tao reset token ngau nhien, luu chi hash/token digest, thoi han va trang thai da dung.
- Backend gui link hoac ma reset qua Amazon SES hoac SMTP da cau hinh.
- Endpoint dat lai mat khau kiem tra token chua het han, chua dung, roi cap nhat password_hash Argon2id.
- Giup API khong bao cac co tai khoan hay khong, gioi han so request/reset, ghi audit log va rotat token sau khi doi mat khau.
- Khong gui token reset plain text qua URL log neu co the tranh duoc.

Day khong nen duoc goi “Cognito lam quen mat khau”. Ban dang tu phat trien phan reset flow va chi dung AWS SES de gui email.

### Lua chon B - Chuyen toan bo sang Amazon Cognito

Dung neu du an muon Amazon quan ly identity lifecycle, user pool, password policy, MFA va email verification.

- Tao mot Cognito User Pool va chuyen register/login/reset sang SDK Cognito.
- Dung Cognito `ForgotPassword` va `ConfirmForgotPassword`.
- Cau hinh Cognito gui email bang default Cognito hoac AWS SES.
- Tach role va profile ung dung trong database hoac JWT custom authorizer claims.
- Migration toan bo user va password chi co the lam khi co password temp/migration strategy; khong the import plaintext password cu.
- Khong nen giu mot luong JWT doc lap va mot luong Cognito song song vi se gay ro nguon identity va loi role/token.

## 5. Khuyen nghi

Voi source hien tai, nen tiep tuc backend JWT/Argon2/PostgreSQL va dung Amazon SES cho Forgot Password. Sau do, moi xem xet chuyen toan bo sang Cognito neu co yeu cau MFA, social login, user pool admin, OIDC federation hoac managed identity lifecycle.

Khong nen chi tao Cognito User Pool rieng de gui mot email reset trong luc backend van luu mat khau va JWT tai PostgreSQL; cach nay se tao hai nguon su that.

## 6. Cong viec tiep theo neu chon luong backend/SES

1. Bo sung request/response schema cho forgot va reset password.
2. Bo sung entity hoac bang reset token voi hash, expiry va used_at.
3. Bo sung endpoint POST forgot/reset.
4. Cau hinh Amazon SES sender domain, sandbox/development status va template email.
5. Them rate limiting va phan biet response chung.
6. Bo sung unit/integration test ve token het han, da dung, email khong ton tai va reset thanh cong.
7. Verify tren moi truong test, khong duoc ket luan hoat dong chi dua tren source code.

## 7. Tinh trang chua xac minh

- Backend chua co implementation reset.
- Amazon SES chua duoc kiem ke/config verify trong pham vi dau vao nay.
- Cognito chua xac minh ton tai o cac Region khac ngoai Singapore/Sydney.
- Khong thuc hien thay doi AWS resource, IAM, database hay source code trong phan tich nay.
