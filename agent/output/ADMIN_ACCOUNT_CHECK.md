# Kiem tra tai khoan admin

Ngay: 2026-11-07

## Muc tieu

Xac dinh trong du an hien tai co tai khoan admin va tai khoan do co the dang nhap duoc hay khong.

## Tai lieu va source da kiem tra

- `database/seed.sql`
- `database/schema.sql`
- `backend/app/services/auth_service.py`
- `backend/scripts/set_user_password.py`
- `docs/local-setup.md`
- `backend/app/models/user.py`

## Ket qua

- Database local dang chay container `learncloud-db`.
- Co mot user admin trong database:
  - ID: 6
  - Email: `admin@example.com`
  - Role: `ADMIN`
- User nay hien **chua co password hash**, nen khong the dang nhap bang email va password.
- `database/seed.sql` cung dinh nghia user admin voi email `admin@example.com`, role `ADMIN`.
- Seed khong dat mat khau cho user.
- Mat khau phai duoc cap qua script:
  `python scripts/set_user_password.py --email admin@example.com`

## Xac minh database

Lenh truy van da duoc chay tren PostgreSQL local:

```sql
SELECT id, email, role, password_hash IS NOT NULL AS has_password
FROM users
WHERE role='ADMIN'
ORDER BY id;
```

Ket qua: `6|admin@example.com|ADMIN|f`, trong do `f` nghia la `password_hash IS NULL`.

## Ket luan

Du an co tai khoan admin, nhung tai khoan admin hien tai chua kich hoat dang nhap vi chua co mat khau. Can dat mat khau cho `admin@example.com` bang script server de tai khoan co the dang nhap.
