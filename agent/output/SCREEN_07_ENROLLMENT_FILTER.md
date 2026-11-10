# Màn 07 — Bộ lọc đăng ký
Ngày: 07/11/2026. Nhánh: feature/hung-ui-review.

## Mục tiêu và tài liệu
Bổ sung ba bộ lọc Tất cả / Đã đăng ký / Chưa đăng ký theo yêu cầu người dùng, SPEC mục 07 và screens/07.png. Đã đọc AGENTS.md, docs/AGENTS.md; đối chiếu CourseListPage, CourseCard, useEnrollments và tests enrollment.

## Thay đổi
- Dùng useEnrollments và API hiện có để lấy đăng ký theo tài khoản; không sửa API/backend.
- Lọc bằng ID khóa học, kết hợp tìm theo tên; giữ từ khóa khi chuyển bộ lọc.
- Khi dữ liệu đăng ký đang tải/lỗi, khóa hai bộ lọc phụ thuộc dữ liệu. Tất cả vẫn xem được; không suy diễn rằng mọi khóa đều chưa đăng ký.
- Hiện lỗi và nút tải lại nếu không tải được đăng ký.
- Card đã đăng ký có nhãn xanh và nút Tiếp tục học, giữ đường dẫn khóa học/lộ trình hiện tại.
- Không sửa màn 10.

## Kiểm chứng
- node --test tests/course-filters.test.cjs tests/enrollment.test.cjs: 5/5 PASS.
- npm.cmd run build: PASS, 108 modules; cảnh báo use client từ react-router không chặn build.
- Không mở trình duyệt. Chưa xác minh hiển thị thực tế và API thật.

## Danh sách file
- frontend/src/pages/CourseListPage.jsx: nối hook và ba bộ lọc, trạng thái tải/lỗi/rỗng.
- frontend/src/components/courses/CourseCard.jsx: prop enrolled, nhãn và CTA.
- frontend/src/styles/student.css: toolbar responsive, bộ lọc và badge.
- frontend/src/utils/courseFilters.js: phép lọc kết hợp.
- frontend/tests/course-filters.test.cjs: kiểm tra phân nhóm, kết hợp từ khóa, ID số/chuỗi, dữ liệu rỗng.
- agent/output/SCREEN_07_ENROLLMENT_FILTER.md: báo cáo này.
- agent/output/UI_SCREENS_01_10_REVIEW.md: ghi chú cập nhật kết quả màn 07.

## Giới hạn / bước tiếp theo
Tìm kiếm vẫn theo tên khóa học, chưa mở rộng sang tên giảng viên. Nghiệm thu trực quan khi được phép kiểm tra trình duyệt.