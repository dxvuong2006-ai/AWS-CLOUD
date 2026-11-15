# Phan tich xung dot xac thuc dependencies.py

Ngay: 2026-11-07

## 1. Muc tieu

Danh gia hai phien ban `get_current_user` trong `backend/app/dependencies.py` va
de xuat cach giai quyet xung dot khong lam moi quan he giua frontend, backend,
role guard va API contract.

## 2. Tai lieu va source da kiem tra

- `backend/app/dependencies.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/tests/unit/test_auth_integration.py`
- `frontend/src/api/client.js`
- `docs/api-contract.md`
- `docs/local-setup.md`
- `README.md`

## 3. Phan tich

### Phien ban JWT hien tai

Phien ban JWT:

- Dung `HTTPBearer(auto_error=False)`.
- Doc Bearer access token tu header `Authorization`.
- Giai ma va kiem tra issuer, audience, signature, expiration va subject trong
  `auth_service.user_from_access_token()`.
- Doc vai tro moi nhat tu ban ghi User trong database.
- Tra 401 cho token thieu, sai ky hieu, het han hoac user da bi xoa.
- Tra 403 cho API khi user co token hop le nhung khong dung role.

Day la co che phu hop voi luong login/register da co trong backend, frontend
dang gui Authorization Bearer, va cac test auth integration trong repository.

### Phien ban X-Demo-User

Phien ban header demo:

- Nhan `X-Demo-User` va chuyen gia tri thanh user ID.
- Khong xac minh mat khau, token, chu ky hoac danh tinh.
- Khong nen dung cho moi truong public vi client co the chon hoac gia mao user ID.
- Chi phu hop lam co che gia lap cho fixture local va smoke test, neu duoc
  gioi han ro rang trong development.

Tai lieu trong repository cung xac nhan `X-Demo-User` chi la co che demo local.
README, API contract va local setup huong toi JWT hoac OIDC/Cognito cho product.

### Loi cua ban ghep xung dot

Ban hien tai dang ket hop dau doc JWT voi phan than tham chi `x_demo_user` ma
khong khai bao tham so Header. Vi vay ban phien ban demo khong the chay xac dinh
vi bien nay chua duoc dinh nghia.

Mot thay doi day du co phai giai quyet merge conflict; khong duoc chi xoa cac
marker conflict ma van giu hai implementation trong cung mot dependency.

## 4. De xuat

Giu implementation JWT lam `get_current_user` duy nhat.

Ly do:

1. Phu hop code frontend dang co luong session/access token.
2. Phu hop endpoint `/auth/login`, `/auth/me` va test auth.
3. Dat role duoc doc tu database thay vi tin role trong client hoac header.
4. Tranh identity impersonation tren moi truong public.

`X-Demo-User` co the giu o mot dependency rieng chi danh cho test local, vi du:

- `get_demo_user` chi duoc dang ky khi `APP_ENV=development`/`ALLOW_DEMO_AUTH=true`.
- Khong import hay dung demo dependency o router production by default.
- Khong cho phep demo dependency override JWT dependency khi chay public API.
- Them test moi rang buoc environment va 401/403 khi demo auth bi tat.

Mot fallback “co token thi JWT, khong co token thi X-Demo-User” khong nen dung:

- Lam API bi phu thuoc vao gia tri header tu client.
- Lam test va hanh vi production khac nhau ngam.
- Gia tang nhieu loi: response 401/403, role matrix va demo script khong nhat quan.
- Thieu ranh gioi ro giua development fixture va production authentication.

## 5. Ket qua kien nghi

- Resolve toi muc JWT cho `get_current_user`, `require_student`,
  `require_instructor` va `require_admin`.
- Xoa import va tham chieu `Header`/`x_demo_user` khoi dependency JWT.
- Kiem tra lai cac test auth bang command backend:
  `python -m unittest discover -s tests/unit -p test_auth_integration.py -v`
- Neu co nhu cau giu demo workflow, tach va dat sau feature flag moi truong;
  khong goi chung trong `get_current_user`.
- Resolve them cac merge conflict marker trong `frontend/src/api/client.js`;
  giu phien ban frontend da dung session/JWT va loai bo doan demo auth conflict.

## 6. Van de chua giai quyet

- Ban ghi chinh phien ban dependencies.md dang co loi bien `x_demo_user` chua khai bao.
- Migration password_hash va cau hinh JWT_SECRET_KEY van phai duoc xac nhan tren
  PostgreSQL local/production truoc khi demo JWT duoc ket luan da hoat dong.
- Frontend hien van co marker merge conflict trong client API va phai duoc resolve
  truoc khi co the xac minh integration thuc te.
- Khong co bang chung kiem thu database/AWS trong phan xung dot nay; ket luan tren
  chi dua tren source va API contract hien tai.

