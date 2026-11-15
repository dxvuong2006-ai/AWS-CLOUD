# Bao cao chinh backend sang Cognito

Ngay: 2026-11-07

## 1. Muc tieu

Bat dau chuyen cac file backend authentication sang Amazon Cognito, giu route frontend
hien co va phan tach JWKS/role mapping/dependencies khoi legacy JWT/Argon2.

## 2. Tai lieu va source da kiem tra

- `backend/app/config.py`
- `backend/app/dependencies.py`
- `backend/app/api/auth.py`
- `backend/app/api/admin.py`
- `backend/app/services/auth_service.py`
- `backend/app/repositories/auth_repo.py`
- `backend/app/schemas/auth.py`
- `backend/app/models/user.py`
- `backend/scripts/set_user_password.py`
- `backend/tests/unit/test_auth_integration.py`
- `database/schema.sql`
- `database/migrations/0003_reconcile_legacy_schema.sql`
- `agent/output/AUTH_CONFLICT_ANALYSIS.md`
- `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md`
- `agent/output/COGNITO_MIGRATION_CODE_CHECKLIST.md`

## 3. Cong viec da thuc hien

### Backend Cognito service

- Them cau hinh User Pool/App Client/Region.
- Them proxy boto3 cho register, login, verify email, resend code, forgot password,
  confirm reset password va change password.
- Them xac minh Cognito JWT RS256 bang JWKS, issuer va client ID/audience.
- Them sync local user bang `cognito_sub`, email va Cognito groups.
- Xoa Argon2/password/JWT issuance khoi auth service chinh.
- Them admin create user, set permanent password, add/remove Cognito group va update attributes.

### API auth

- `/auth/register` trao doi voi Cognito SignUp.
- `/auth/login` trao doi voi Cognito InitiateAuth.
- `/auth/verify-email`, `/auth/resend-verification`,
  `/auth/forgot-password`, `/auth/reset-password` da duoc ket noi endpoint.
- `/auth/me` xac minh Cognito Bearer token thay HS256 backend.
- `/auth/change-password` goi Cognito ChangePassword.
- Giữ gia tri tra ve va route frontend cu tren API contract.

### Admin va repository

- Admin create user khong tao `local:<uuid>` va khong luu password hash.
- Admin update role dong bo Cognito groups.
- Repository bo sung find/create theo `cognito_sub`.
- Script set password chuyen sang Cognito AdminSetUserPassword.

### Database/test

- Them migration `0004_cognito_auth_cutover.sql` chuan bi cutover auth.
- Test auth integration da bo HS256/Argon2 va mock Cognito Bearer token.
- Khai bao Cognito placeholder trong offline unit settings.

## 4. Ket qua verify

- `py -3 -m compileall backend\app backend\scripts`: thanh cong; toan bo Python backend
  va script compile duoc ma khong co loi cu phap.
- Cai dependencies bang `py -3 -m pip install -r backend\requirements.txt` khong
  hoan tat vi Python 3.13 moi truong hien tai khong build duoc pydantic-core 2.14.5
  tu Pin cu; issue nay chua bang chung runtime/auth loi.
- Khong chay live Cognito vi chua co User Pool/App Client/credential AWS duoc xac minh
  trong pham vi nay.
- Khong deploy hoac thay doi AWS resource.

## 5. Van de chua giai quyet

- Can tao User Pool/App Client/SES va cap ba `COGNITO_*` environment.
- Can bat user pool app client USER_PASSWORD_AUTH neu frontend/backend dung login
  password flow hien tai.
- Existing users chua mapping `cognito_sub`; can migration/import va reset password.
- Cognito user group va PostgreSQL role can co mot nguon dong bo chinh thuc.
- Admin email update can xet lai neu email la Cognito username sign-in alias.
- Chua co live E2E register/login/reset/email verification.
- Chua co ban jwt RS256 thuc te trong test offline; can test voi mocked JWKS va token.

## 6. Phan chua can chinh frontend

- Frontend van goi cac route backend hien co; backend da cung cap proxy Cognito nen
  chua bat buoc doi auth SDK ngay trong dot backend nay.
- Tuy nhien frontend van luu JWT/backend token trong session va se tra ve Cognito
  token sau login; route `/auth/me` da xac minh token nay.

## 7. Cong viec tiep theo

1. Cau hinh/tao Cognito User Pool bang quyen Dung va region `ap-southeast-1`.
2. Cap app client ID/region/user pool ID vao backend production environment.
3. Migration mapping existing users va quyen reset password.
4. Test mocked JWKS token va mocked boto3 luong forgot/reset/admin.
5. Chay integration Cognito staging bang account test, khong dung production.
6. Sau khi pass staging, xoa legacy password_hash va endpoint path demo/HS256.
