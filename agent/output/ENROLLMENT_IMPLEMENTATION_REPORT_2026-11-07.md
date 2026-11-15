# Bao cao hoan thien dang ky khoa hoc

## Ngay

2026-11-07

## Muc tieu

Hoan thien luong dang ky khoa hoc o real mode bang cach bo sung endpoint lay danh sach khoa hoc da dang ky va dong bo xu ly 409 o giao dien.

## Tai lieu va source code da kiem tra

- `frontend/src/pages/CourseDetailPage.jsx`
- `frontend/src/api/enrollments.api.js`
- `frontend/src/hooks/useEnrollments.js`
- `backend/app/api/enrollments.py`
- `backend/app/services/enrollment_service.py`
- `backend/app/repositories/enrollments_repo.py`
- `backend/app/schemas/enrollment.py`
- Cac model Course, Section, Lesson, LessonProgress, Enrollment, Quiz va QuizAttempt.
- Bao cao reconcilication frontend hien co.

## Cong viec da thuc hien

- Bo sung `GET /students/me/courses`.
- Chi cho STUDENT truy cap endpoint danh sach dang ky.
- Lay chi khoa hoc PUBLISHED trong danh sach cua student.
- Tra ve course metadata, trang thai hoc, ti le hoan thanh, lesson tiep tuc va cac section mo khoa.
- Tinh section mo khoa dua tren quiz checkpoint da duoc pass.
- Them schema Pydantic cho response enrollment.
- Them repository function truy van enrollment cua student.
- Cap nhat `CourseDetailPage` de 409 nghia la da dang ky duoc xu ly nhu success va reload enrollment thay vi hien loi.
- Them unit test cho endpoint danh sach va kiem tra role.
- Gioi han dependency `httpx` trong mien tuong thich voi FastAPI TestClient cua du an (`>=0.24,<0.28`).

## Ket qua va bang chung kiem thu

- Frontend production build: pass.
- Frontend unit tests: 41/41 pass.
- Compile four changed backend Python modules: pass.
- Enrollment API focused tests: 2/2 pass.
  - STUDENT nhan response 200 voi dung response shape.
  - INSTRUCTOR nhan 403.
- Full backend offline suite: da chay va con 51 failures, 22 errors. Cac loi duoc quan sat chu yeu lien quan cac module/baseline o ngoai thay doi enrollment (vi du module `ai_pipeline` khong ton tai va mock `S3StorageAdapter` khong co trong review service); khong doi toi ket luan endpoint enrollment nhu da test tap trung.

## Van de chua giai quyet

- Backend progress/media van la mot module rieng va chua duoc khai bao trong endpoint nay.
- Cac trang instructor/admin van co the hien tai API roadmap; task nay tap trung vao blocker enrollment.
- Full backend suite chua dat xanh do cac baseline failures ngoai thay doi nay.
- Chua co test thuc te service voi database cho toan bo row enrollment/lesson/quiz; focused API test hien mock service shape.

## Cong viec tiep theo

- Kiem tra endpoint enrollment voi database va du lieu seeded thuc.
- Viet integration test sau enroll de 1 student xuat hien trong danh sach.
- Bo sung integration test cho enroll duplicate 409 va course unpublished.
- Nguoi phu trach Huy tiep tuc kiem tra contract backend va auth.
- Nguoi phu trach Dung verify endpoint tren AWS/test environment neu da deploy.
