# Chỉnh giao diện màn 11–20 và hiệu ứng lật flashcard
Ngày: 07/11/2026. Nhánh: feature/hung-ui-review.

## Phạm vi
Đã đọc AGENTS.md, docs/AGENTS.md, SPEC mục 11–20 và trực tiếp xem đủ ảnh 11.png–20.png. Chỉ chỉnh JSX/CSS, dùng dữ liệu, state, callback, điều kiện và API hiện có.

## Thay đổi
- 11: thông tin giảng viên/tiến độ trên tiêu đề; marker section; căn dòng bài học, trạng thái đã học, bài tiếp tục và hàng checkpoint.
- 12: kích thước video, panel transcript, khoảng cách tóm tắt; giữ native video controls và toàn bộ xử lý tiến độ.
- 13: hai nút quay lại/checkpoint đặt cùng hàng; giữ điều kiện khóa và nút kiểm tra quyền.
- 14–15: hai mặt flashcard thật, CSS perspective/rotateY, chuyển động 560ms; dùng flipped/setFlipped hiện có. Nút lật luôn có thể dùng bàn phím; nội dung mặt ẩn không đọc trùng; hỗ trợ reduced motion.
- 16: icon check SVG, bố trí hai thống kê và nhóm nút; giữ cảnh báo quyền checkpoint và ôn lại tất cả.
- 17–18: căn thẻ trước khi bắt đầu, vùng câu hỏi/đáp án, sidebar tiến độ, nhãn Điểm đạt.
- 19: icon cảnh báo SVG, giữ số câu trả lời, nút và callbacks nộp/hủy.
- 20: điểm và badge ở trái, chi tiết câu ở phải; dùng details để thu gọn câu đúng và vẫn xem được toàn bộ đáp án/giải thích. Khái niệm cần xem lại vẫn truy cập được.

## Giới hạn
Không thêm điểm checkpoint giả hoặc suy ra Đạt từ số lesson đã xem. Không thêm điều hướng section tiếp theo hoặc API mới. Luồng ôn AI/khóa checkpoint được giữ nguyên.
Không chạy build/test, không mở trình duyệt, không rà soát sau sửa theo yêu cầu người dùng. Chưa xác nhận hiển thị pixel-perfect hoặc chạy thực tế.

## File
- frontend/src/pages/CourseDetailPage.jsx
- frontend/src/pages/FlashcardPage.jsx
- frontend/src/pages/CheckpointPage.jsx
- frontend/src/components/courses/CourseOutline.jsx
- frontend/src/components/learning/FlashcardDeck.jsx
- frontend/src/components/learning/flashcard.css
- frontend/src/components/learning/TranscriptPanel.jsx
- frontend/src/components/learning/SummaryPanel.jsx
- frontend/src/components/learning/SectionGate.jsx
- frontend/src/components/quiz/QuizNavigator.jsx
- frontend/src/components/quiz/SubmitConfirmDialog.jsx
- frontend/src/components/quiz/QuizResult.jsx
- frontend/src/styles/student.css
- agent/output/UI_SCREENS_11_20_IMPLEMENTATION.md (báo cáo tổng hợp)

## Bước tiếp theo
Nghiệm thu giao diện và chạy kiểm thử khi người dùng yêu cầu.