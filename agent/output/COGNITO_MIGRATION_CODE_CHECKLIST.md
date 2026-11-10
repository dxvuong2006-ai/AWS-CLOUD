# Chuyen toan bo authentication sang Amazon Cognito

Ngay: 2026-11-07

## 1. Muc tieu

Tong hop cac phan code va cau hinh can thay doi neu LearnCloud chuyen toan bo
register, login, email verification, password reset va authorization sang Amazon
Cognito.

## 2. Tai lieu va source da kiem tra

- `backend/app/api/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/dependencies.py`
- `backend/app/config.py`
- `backend/app/models/user.py`
- `backend/app/repositories/auth_repo.py`
- `backend/app/api/admin.py`
- `backend/app/main.py`
- `backend/scripts/set_user_password.py`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/api/auth.api.js`
- `frontend/src/api/client.js`
- `frontend/src/api/session.js`
- `frontend/src/pages/AccountPages.jsx`
- `frontend/src/pages/AdminUsersPage.jsx`
- `frontend/src/mocks/account.mock.js`
- `frontend/package.json`
- `backend/requirements.txt`
- `database/schema.sql`
- `database/migrations/`
- `backend/tests/unit/test_auth_integration.py`
- `agent/output/AUTH_CONFLICT_ANALYSIS.md`
- `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md`

## 3. Ket luan hien tai

He thong dang dung JWT HS256 tu FastAPI, password Argon2id trong PostgreSQL va
role trong database. Frontend dang luu access token trong session storage va gui
token qua header Bearer.

Model User da co cot `cognito_sub`, nhung:

- Gia tri hien tai duoc tao nhu `local:<uuid>` khi dang ky local.
- `password_hash` van duoc dung va luu khi dang ky/admin tao user.
- Chua co environment/config Cognito.
- Chua co code xac minh Cognito JWT.
- AWS inventory khong xac nhan User Pool da cau hinh san sang o Singapore/Sydney.

## 4. Cau hinh AWS cau phai chuan bi

1. Tao Cognito User Pool o `ap-southeast-1`.
2. Cau hinh email/username authentication bang email.
3. Bat email verification.
4. Tao app client khong dung client secret neu React goi SDK truc tiep.
5. Cau hinh password policy va MFA theo yeu cau san pham.
6. Cau hinh Cognito Groups: `STUDENT`, `INSTRUCTOR`, `ADMIN`.
7. Cau hinh SES hoac Cognito default email neu email cung cap khong san sang.
8. Cau hinh callback/logout URL cho local va production frontend.
9. Neu dung API Gateway, tao Cognito authorizer va map claim sang backend.
10. Khong thay doi IAM/AWS cho den khi co yeu cau va quyen deploy.

De tranh hai nguon su that ve role, danh sach role nen lay tu Cognito groups va
dong bo sang cot `role` cua PostgreSQL. Khong tin cac gia tri role gui len tu
frontend hoac user data ky sai trong ID token.

## 5. Backend can thay doi

### 5.1. Cau hinh

Trong `backend/app/config.py`, bo cac truong JWT production va bo sung:

- `COGNITO_USER_POOL_ID`
- `COGNITO_APP_CLIENT_ID`
- `COGNITO_REGION`
- `COGNITO_ISSUER`
- `COGNITO_JWKS_URL`

Khong luu client secret, password, Access Key, credential AWS trong source hay
`.env` versioned.

### 5.2. Auth service

`backend/app/services/auth_service.py` se khong con:

- PyJWT HS256 decode.
- JWT secret issuance.
- Argon2 password hashing/verification.
- Legacy login bang email/password.
- `issue_access_token()`.

Thay bang module validate Cognito token:

- Lay JWKS cua User Pool va cache key theo `kid`.
- Xac minh issuer, audience/app client, signature, expiration va token_use.
- Loc token claims `sub`, `email`, `cognito:groups`, `cognito:username`.
- Hay dung ID token cho claims user va access token cho authorization API; can
  phan biet scope va cach API Gateway/HTTP bearer xu ly tung loai.
- Cung cap ma loi 401 cho token thieu/sai/het han va 403 cho group/role thieu.

### 5.3. Dependencies

`backend/app/dependencies.py` se:

- Bearer token Cognito thay vi token HS256 cua backend.
- Lay User local thong qua `cognito_sub`, sau do fallback email neu migration dang
  chuyen dan va tao lien ket mot lan co kiem soat.
- Khong truy van mat khau hay database password hash.
- Doc role tu Cognito group claim hoac role da dong bo trong database; chon mot
  nguon su that va kiem tra lau.
- Giu `require_student`, `require_instructor`, `require_admin` voi logic role
  trong token claim hoac user da dong bo.
- Xoa fallback/demo identity neu production.

### 5.4. Auth router

`backend/app/api/auth.py` can quyet dinh 2 kien truc:

#### A. Frontend goi truc tiep Cognito SDK

Backend chi giu:

- `GET /auth/me`
- Update profile
- Dependency verify Cognito token

Khong giu `/auth/login`, `/auth/register`, `/auth/verify-email`,
`/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`.

#### B. Backend proxy Cognito

Backend giu cung API hien tai va dung boto3:

- `sign_up`
- `initiate_auth`
- `confirm_sign_up`
- `resend_confirmation_code`
- `forgot_password`
- `confirm_forgot_password`
- `change_password`
- `admin_create_user`
- `add_user_to_group`

Lua chon nay khong nen luu password plaintext trong backend log/database. Lua
chon A giam du lieu nhay cam va gioi han quyen AWS cua API server, nhung doi
frontend thay doi lon hon.

Khuyen nghi frontend dung Cognito SDK/Amplify Auth voi backend chi xac minh JWT.

### 5.5. Admin user management

`backend/app/api/admin.py` can thay:

- Bo `hash_password(payload.password)` va tao `local:<uuid>`.
- Goi Cognito AdminCreateUser cho tai khoan Instructor/Admin.
- Cap Cognito group khi tao/chinh role.
- Them Cognito Group khi patch role.
- Xoa group cu khi patch role sang role khac.
- Chen/cap nhat User PostgreSQL bang `cognito_sub`.
- Xoa password form cua frontend khi user moi vi Cognito quan ly password.

### 5.6. Script/admin operations

`backend/scripts/set_user_password.py` khong nen sua password trong database nua.
Thay bang Cognito operation phu hop, vi du:

- `admin_set_user_password`
- Hoac AdminResetUserPassword flow theo policy.

## 6. Database can thay doi

Cot `cognito_sub` can tro thanh mapping user bat buoc sau migration. Password
Hash khong con la chuoi su that cho authentication va co the:

- Xoa migration long-term password_hash neu tat ca user da chuyen.
- Hoac de cot nullable tam thoi cho migration, danh dau legacy va xoa sau.

Can migration moi:

1. Khong duoc gan random `cognito_sub` moi nhu `local:<uuid>` vao user thuc su.
2. Tao user Cognito va mapping `sub` cho tung user legacy.
3. Validate thay doi email/role roi moi link.
4. Khong the import password cu tu Argon2 sang Cognito; khong co plaintext va
   Cognito khong ho tro import truc tiep hash Argon2 theo kieu nay.
5. Yen cau user doi password mot lan hoac su dung custom migration Lambda neu
   Argon2 and SaaS flow duoc ho tro va thiet ke mat sau.

Tao transaction migration/co-so du lieu bo:

- `cognito_sub NOT NULL` sau khi migration hoan tat.
- Unique index da co tren `cognito_sub`.
- Password-related columns removed/deprecated.

## 7. Frontend can thay doi

### 7.1. Dependency va environment

Them package Cognito phu hop:

- Khuyen nghi `aws-amplify` voi subpath auth API, hoac SDK Cognito the UI SDK.

Bo sung `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_APP_CLIENT_ID`,
`VITE_COGNITO_REGION`, `VITE_COGNITO_DOMAIN` neu dung Hosted UI.

Khong dat AWS secret/client secret vao bien `VITE_*`.

### 7.2. Auth API/session/context

`frontend/src/api/auth.api.js` can:

- Register: `signUp`
- Verify: `confirmSignUp`
- Resend: `resendSignUpCode`
- Login: `signIn`
- Forgot: `resetPassword`
- Confirm reset: `confirmResetPassword`
- Change password: `updatePassword`
- Logout/signOut.

`frontend/src/context/AuthContext.jsx` can:

- Lay session Cognito/token va current user Cognito.
- Luu ID/access/refresh token theo SDK hoac memory; khong tu implement storage
  chua tot.
- Refresh token tu Cognito va refresh expiration tu session that.
- Logout qua Cognito signOut.
- Goi `/auth/me` sau login de lay profile va role database.
- Xu ly hop le cho user CHUA verified va SESSION expired.

`frontend/src/api/session.js` chuyen sang session/helper Cognito hoac chi luu
metadata app; khong luu plain Cognito refresh token tuy y neu SDK da quan ly.

`frontend/src/api/client.js` lay Cognito access/ID token moi va gui Bearer;
khong giu mock `mock:<id>:<version>` cho luong production.

### 7.3. Account pages

`frontend/src/pages/AccountPages.jsx` da co UI phu hop:

- Register page.
- Verify email page.
- Forgot password page.
- Reset password page.
- Change password/profile behavior.

Chi can thay action implementation, khong bat buoc doi route. Cap nhat thong bao
error tu Cognito sang thong diep user-safe, retry/cooldown va ma loi.

`frontend/src/pages/LoginPage.jsx` thay logout/login implementation qua auth
context; giu UI va role redirect.

### 7.4. Admin page

`frontend/src/pages/AdminUsersPage.jsx` va admin API:

- Create user khong du password ben client neu dung AdminCreateUser.
- Role phai chay qua backend/Cognito.
- Gan vai tro moi va refresh danh sach user.
- Khong cho user client sua Cognito group/token role.

### 7.5. Mock

`frontend/src/mocks/account.mock.js` va `AUTH_MOCK` chi duoc giu cho local
development sau khi production auth da done. Mock password/khang email co the
van dat, khong duoc dung mock API de override production Cognito.

## 8. API Gateway va hạ tầng

Neu API Gateway nam truoc FastAPI, chuyen:

- AuthorizationType `NONE` thanh Cognito authorizer hoac Lambda authorizer.
- Authentication voi Cognito JWT ID token/access token theo cau hinh authorizer.
- Map Cognito claims vao headers can backend neu authorizer ho tro.
- Cors/allowed origin production.
- API Gateway stage khong chua token log.

Can kiem tra deployment version backend va RDS/Security Group truoc khi deploy.

## 9. Test can thay doi

Trong `backend/tests/unit/test_auth_integration.py` va cac test lien quan:

- Xoa test login HS256/Argon2.
- Mock JWKS va Cognito claims thay vi pyjwt local secret.
- Test sai issuer, audience, signature, expiry, sub va token_use.
- Test role group va database role mapping.
- Test local/mock/demo auth bi tu choi.
- Test migration `cognito_sub`.
- Test `/auth/me`, create/update/admin roles voi token Cognito.

Frontend can them unit/browser test cho:

- Register.
- Email verification/resend.
- Login Cognito.
- Forgot/reset/change password.
- Refresh token.
- Logout.
- ProtectedRoute va Unauthorized handling.

## 10. Thu tu migration khuyen nghi

### Giai doan 1: Infrastructure va account

- Tao Cognito User Pool/app client/groups/email.
- Cap bien moi va AWS profile deploy.

### Giai doan 2: Backend dual-mode kiem soat

- Them validate Cognito JWT.
- Giu local JWT tam thoi chi de migration neu co feature flag cho phep.
- Bo fallback public khi complete cutover.

### Giai doan 3: Database mapping

- Migration bang `cognito_sub`.
- Gan/sub mapping cho existing user.
- Quyet dinh legacy `password_hash` nullable/deprecated.
- Thong bao user reset password lan dau neu khong the migration password.

### Giai doan 4: Frontend

- Them Cognito SDK.
- Thay AuthContext/auth.api/session/client.
- Xoa flow password sang backend HS256.
- Chuyen mock production ket thuc.

### Giai doan 5: Admin va AWS

- Tao admin/instructor/role qua Cognito groups.
- Gan Cognito authorizer cho API Gateway neu su dung.
- Deploy va test E2E tren staging.

### Giai doan 6: Cutover

- Disable legacy JWT endpoints va secret.
- Xoa HS256/Argon2 code neu khong con legacy user.
- Xoa password_hash va set_user_password.
- Revocation: token cu het han hoac xoa app client/flow cu.

## 11. Checklists theo file

### Backend

- `app/config.py`: bo JWT secret, them Cognito config.
- `app/services/auth_service.py`: thay HS256/Argon2 bang Cognito JWKS verify va user sync.
- `app/dependencies.py`: verify bearer Cognito va map user/role.
- `app/api/auth.py`: dua auth operations sang Cognito SDK hoac proxy.
- `app/api/admin.py`: tao user/group qua Cognito thay database password hash.
- `app/models/user.py`: keep/strengthen `cognito_sub`; deprecate/remove `password_hash`.
- `app/repositories/auth_repo.py`: tim/tao theo `cognito_sub` va email.
- `scripts/set_user_password.py`: thay Cognito admin password operation.
- `requirements.txt`: co the bo argon2-cffi va PyJWT neu khong con legacy; giu PyJWT neu validate JWKS bang JWT library.
- `tests/unit/test_auth_integration.py`: thay test JWT va password.

### Frontend

- `package.json`: them Cognito SDK/Amplify Auth.
- `src/context/AuthContext.jsx`: Cognito session lifecycle.
- `src/api/auth.api.js`: mapping operation sang Cognito.
- `src/api/session.js`: stored session va refresh.
- `src/api/client.js`: Cognito bearer token.
- `src/pages/AccountPages.jsx`: action implementation.
- `src/pages/LoginPage.jsx`: Cognito login context.
- `src/pages/AdminUsersPage.jsx`: khong gui password sang DB admin API.
- `src/mocks/account.mock.js`: chi development-only.

### Database/docs/infra

- `database/schema.sql`: thay/hien DINH LAI `cognito_sub`; `password_hash` nullable/deprecated.
- Tao migration moi voi mapping existing users.
- `docs/api-contract.md`: cap nhat auth contract va OAuth/JWT claims.
- `docs/local-setup.md`, `docs/aws-deployment.md`: cau hinh Cognito.
- Infrastructure: User Pool, app client, SES, API authorizer va IAM.

## 12. Van de chua xac minh

- User Pool/app client chua xac nhan trong inventory AWS hien co.
- Chua co quyen deployment IAM cho User Pool/API Gateway.
- User Pool domain/app callback URLs chua duoc xac nhan.
- Chua chot ID token hay access token cho API authorization.
- Chua co schema migration mapping existing users.
- Chua xac dinh duoc Cognito MFA/password policy.
- Chua co migration password cho existing users.

Khong nen ket luan “da chuyen sang Cognito” khi moi thay frontend SDK ma backend
van HS256 hoac database van la nguon password; can hoan tat flow va bat pilot
staging truoc khi cutover production.
