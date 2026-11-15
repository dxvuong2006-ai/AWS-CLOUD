# Navbar Logo and Collapse Report

## 1. Ngay thuc hien
2026-11-07

## 2. Muc tieu
- Thay chu L va logo tam thoi tren navbar bang logo LearnCloud trong `src/public/logo.png`.
- Bo sung nut dong/mo navbar va dong bo khoang cach noi dung.

## 3. File da kiem tra
- frontend/src/components/layout/Navbar.jsx
- frontend/src/components/layout/Navbar.css
- frontend/src/App.jsx
- frontend/src/routes/AppRouter.css
- frontend/src/styles/student.css
- frontend/src/public/logo.png

## 4. Cong viec da thuc hien
- Navbar hien tat ca role bang logo LearnCloud tu `logo.png`.
- Bo sung nut thu gon sidebar ben tren desktop.
- Bo sung nut mo/dong menu tren mobile.
- Trang thai thu gon duoc quan ly tai App va dong bo class `app-shell--collapsed`.
- Noi dung chinh thay margin khi navbar tu 240px/260px xuong 72px tren desktop.
- Sua mobile CSS de menu hien/ an theo nut thay vi luon hien.

## 5. Ket qua
- Frontend production build: PASS.
- Frontend unit tests: 41/41 PASS.

## 6. Van de chua giai quyet
- Khong co browser page duoc chia se nen chua chup/quan sat truc quan bang Playwright trong phien nay.

## 7. Cong viec tiep theo
- Mo app tai `http://localhost:5173` va kiem tra giao dien logo/collapse o cac viewport desktop/mobile.
