# Đối chiếu và chỉnh giao diện màn 01–10

Ngày: 07/11/2026. Nhánh: feature/hung-ui-review.
Trạng thái: READY_FOR_TEST — đã kiểm tra source/build; chưa kiểm tra hiển thị bằng trình duyệt.

## Phạm vi và tài liệu
- Đọc AGENTS.md, docs/AGENTS.md, SPEC mục 01–10 và trực tiếp xem đủ ảnh docs/ui-doc/ui-spec/screens/01.png đến 10.png.
- Kiểm tra JSX/CSS hiện tại, dữ liệu courses/enrollments và khung học viên.
- agent/input có LearnCloud_UI_Design_Spec_v3.pdf nhưng môi trường thiếu thư viện trích xuất PDF; dùng SPEC và ảnh v4 được người dùng chỉ định làm chuẩn trực tiếp.
- Không kiểm tra hay thay đổi AWS; không thay đổi API, nghiệp vụ xác thực, đăng ký khóa học, tính tiến độ hoặc điều kiện mở khóa.

## Kết quả từng màn
| Màn | Đối chiếu / thay đổi |
| --- | --- |
| 01 | Code đã có bố cục hai cột 39.5/60.5, form rộng 418px, nút và link theo ảnh. Bổ sung viền thông báo thành công. Không đổi xử lý đăng nhập. |
| 02 | Icon mắt trước đây chỉ là SVG tĩnh; chuyển thành nút ẩn/hiện mật khẩu có aria-label và aria-pressed. Giữ nguyên validation và submit. |
| 03 | Định dạng thời gian gửi lại mã mm:ss, tách màu nút và bộ đếm, căn giữa phần đổi email phụ trợ, làm rõ focus của ô OTP. Giữ nguyên cooldown và mã xác minh. |
| 04 | Bố cục icon thành công, tiêu đề, mô tả hai dòng và nút đăng nhập đã có; không sửa JSX. |
| 05 | Form email, mô tả và nút gửi mã đã tương ứng ảnh; không sửa JSX. |
| 06 | Dùng nút mắt hoạt động giống màn 02; định dạng bộ đếm gửi lại mã. Giữ nguyên reset, validation và điều hướng. |
| 07 | Thêm icon tìm kiếm; chỉnh khoảng cách thẻ, biểu tượng theo chủ đề, avatar giảng viên hai chữ cái. Giữ nguyên tìm kiếm theo tên khóa học. |
| 08 | Hiển thị learning_objectives có sẵn thành danh sách thay vì luôn lặp mô tả; fallback mô tả nếu không có mục tiêu. Thay avatar GV bằng chữ viết tắt tên, dùng icon chủ đề khóa học. |
| 09 | Icon check trong vòng tròn; nút Để sau và Bắt đầu học đúng thứ tự ảnh. Cả hai đóng dialog theo hành vi hiện có để lộ trang khóa học/lộ trình; giữ link Khóa học của tôi ở dòng phụ. |
| 10 | Hiển thị tên giảng viên từ dữ liệu thay vì chỉ có trạng thái; đổi icon theo chủ đề, căn nút tiếp tục học và link phụ. Giữ nguyên bốn bộ lọc và cách lọc hiện có. |

## Kiểm chứng
- npm.cmd run build: PASS (107 modules); cảnh báo use client của react-router, không làm build thất bại.
- node --test tests/accounts.test.cjs tests/auth.test.cjs tests/enrollment.test.cjs: 9/9 PASS.
- git diff --check: PASS; Git báo chuẩn hóa LF/CRLF.
- Không mở trình duyệt, không chạy browser tests, không xác nhận pixel-perfect hay luồng API thật.

## Khác biệt còn lại và giới hạn
- Màn 07 chưa có logic lọc Đã đăng ký / Chưa đăng ký, trạng thái enrollment trên card và tìm theo giảng viên; không thêm nút giả hoặc gọi API mới trong đợt sửa giao diện.
- Màn 08 không gán nhãn Miễn phí khi dữ liệu chưa cung cấp giá; mục tiêu và tên giảng viên hiển thị theo dữ liệu thực, không chép dữ liệu ví dụ từ ảnh.
- Màn 09 Bắt đầu học giữ hành vi đóng dialog để xem lộ trình tại trang khóa học; không thêm route hay tự chọn lesson.
- Màn 10 giữ Tất cả / Chưa học / Đang học / Hoàn thành để không đổi logic lọc, khác mẫu chỉ có hai tab.
- Các link phụ đổi email, gửi lại mã, thông báo mock và lỗi vẫn giữ để không mất chức năng hiện tại.
- Khung học viên và chức năng thu gọn sidebar hiện tại được giữ nguyên.
- Cần nghiệm thu trực quan và kiểm tra luồng API thật ở đợt được cho phép; nếu muốn khớp đầy đủ các chức năng còn thiếu, cần triển khai riêng logic tương ứng.

## Danh sách file
- frontend/src/pages/AccountPages.jsx: nút mắt và định dạng bộ đếm.
- frontend/src/pages/login.css: trạng thái và căn chỉnh form.
- frontend/src/pages/CourseListPage.jsx: icon tìm kiếm và placeholder đúng khả năng hiện có.
- frontend/src/pages/CourseDetailPage.jsx: mục tiêu học tập, avatar, dialog.
- frontend/src/pages/MyCoursesPage.jsx: thông tin giảng viên và artwork.
- frontend/src/components/courses/CourseCard.jsx: artwork và avatar.
- frontend/src/components/courses/CourseArtwork.jsx: SVG trình bày dùng chung (mới).
- frontend/src/styles/student.css: căn chỉnh riêng màn 07–10.
- agent/output/UI_SCREENS_01_10_REVIEW.md: báo cáo tổng hợp này.
Cập nhật 07/11/2026: Đã bổ sung bộ lọc đăng ký và nhãn enrollment cho màn 07 theo yêu cầu tiếp theo. Giới hạn thiếu bộ lọc nêu trên đã được xử lý; xem SCREEN_07_ENROLLMENT_FILTER.md. Màn 10 giữ nguyên.
