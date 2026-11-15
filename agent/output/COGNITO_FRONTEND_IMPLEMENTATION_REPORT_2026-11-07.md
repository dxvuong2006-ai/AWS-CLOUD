# Bao cao chinh frontend sang luong Cognito

Ngay: 2026-11-07

## 1. Muc tieu

Cap nhat frontend de su dung backend proxy Cognito, dam bao hai luong verification
gui ma va nhap ma 6 chu so cho xac minh email va dat lai mat khau.

## 2. Tai lieu va source da kiem tra

- `frontend/src/api/auth.api.js`
- `frontend/src/api/client.js`
- `frontend/src/api/session.js`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/pages/AccountPages.jsx`
- `frontend/src/pages/LoginPage.jsx`
- `frontend/src/utils/accountErrors.js`
- `frontend/src/mocks/account.mock.js`
- `frontend/tests/accounts.test.cjs`
- `frontend/tests/auth.test.cjs`
- `backend/app/api/auth.py`
- `backend/app/services/auth_service.py`

## 3. Cong viec da thuc hien

### API va Bearer token

- Sua API client de gui token theo header `Authorization: Bearer <token>`.
- Tang ApiError de giu machine-readable Cognito code va user detail.
- Normalized email cho login, register, verify, resend, forgot va reset.
- Chuyen luong mot cach khong bat buoc frontend SDK vi backend dang proxy Cognito.

### Mã xác thực

- Ma xac minh email chi chap nhan du dung 6 chu so truoc khi gui backend.
- Ma reset chi chap nhan du dung 6 chu so.
- Input ma xac minh tu dong loai bo ky tu khong phai chu so va gioi han 6.
- Trang verify va reset van giu cooldown va nut gui lai ma.
- Forgot password luon tra thong diep trung tinh; backend khong leak user khong ton tai.

### Mat khau

- Frontend kiem tra mat khau 8-128 ky tu.
- Frontend yeu cau it nhat mot chu va mot chu so.
- Kiem tra confirm password truc tiep truoc khi goi API.
- Dang ky, reset va doi mat khau dung cung password policy phia frontend.

### Thong bao loi

- Mapping loi Cognito: not confirmed, not authorized, expired/code mismatch,
  duplicate email, too many request va limit exceeded.
- Backend tra code/message co cau truc thay vi chi tra raw detail string.

### Mock

- Mock authentication chi kich hoat khi ca hai flag mock duoc bat.
- Production build khong duoc phep goi mock khi chi moi `VITE_USE_AUTH_MOCK=true`.
- Mock van ho tro ma 6 so va reset invalidates old session.

## 4. Ket qua kiem thu

- `npm.cmd run build`: thanh cong, Vite build 106 modules va tao bundle frontend.
- `npm.cmd test`: thanh cong, 41/41 test pass.
- Da test auth account mock: register requires verification, reset invalidate session,
  expired code va repeated guesses rejected.
- Chua co live browser/Cognito test vi User Pool/App Client/SES chua duoc cau hinh.

## 5. Van de chua giai quyet

- Chua co Cognito User Pool/App Client thuc te.
- Backend can AWS IAM quyen Cognito de goi runtime API.
- Cac luong flow chua duoc verify E2E voi email thuc.
- Frontend chua dung SDK Amplify truc tiep, dang dung backend proxy theo kien truc da chot.
- Chua co browser smoke test moi cho 6-digit Cognito code.

## 6. Cong viec tiep theo

1. Nhan User Pool ID/App Client ID/SES sender da Dung/Admin cau hinh.
2. Chay staging voi tai khoan test va email verified.
3. Xac minh `/auth/register`, `/auth/verify-email`, `/auth/resend-verification`,
   `/auth/forgot-password`, `/auth/reset-password` va `/auth/login`.
4. Xac minh old session/session storage het han sau reset va change password.
5. Chot migration existing users va production cutover.
