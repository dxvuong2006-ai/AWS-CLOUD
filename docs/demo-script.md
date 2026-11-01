# Kịch bản demo local — phạm vi hiện tại

Thời lượng: 4–6 phút. Kịch bản này chỉ dùng các route đã đăng ký trong FastAPI
và dữ liệu seed. Nó không khẳng định progress, quiz, AI review, Tutor hay
pipeline AWS đã sẵn sàng; các phần đó chưa phải demo gate của repository hiện
tại.

## 0. Chuẩn bị

Hoàn tất [local setup](local-setup.md) trên database sạch, sau đó chạy backend
và frontend. Trong PowerShell mới, lấy ID từ seed và tạo header dùng lại:

```powershell
$api = "http://127.0.0.1:8000"
$instructorId = (docker exec learncloud-db psql -U learncloud -d learncloud -tAc "SELECT id FROM users WHERE email = 'instructor@example.com'").Trim()
$studentId = (docker exec learncloud-db psql -U learncloud -d learncloud -tAc "SELECT id FROM users WHERE email = 'student@example.com'").Trim()
$awsCourseId = (docker exec learncloud-db psql -U learncloud -d learncloud -tAc "SELECT id FROM courses WHERE title = 'Introduction to AWS' LIMIT 1").Trim()
$instructorHeaders = @{ "X-Demo-User" = $instructorId }
$studentHeaders = @{ "X-Demo-User" = $studentId }
```

Kiểm tra `$instructorId`, `$studentId`, `$awsCourseId` đều có giá trị. Các
header trên là cơ chế demo local; không dùng cho demo/public production.

## 1. Mở đầu: hệ thống đang hoạt động — 30 giây

1. Mở `http://127.0.0.1:8000/docs`; nói rõ đây là contract thực thi hiện tại.
2. Chạy health check:

   ```powershell
   Invoke-RestMethod "$api/health"
   ```

   Kỳ vọng: `status : ok`.
3. Mở `http://localhost:5173` và cho thấy danh sách course. Nếu frontend đang
   đặt mock mode, dùng `/docs` cho bước API còn lại để tránh nhầm mock với dữ
   liệu backend.

## 2. Student xem course đã publish — 1 phút

1. Lấy course public:

   ```powershell
   Invoke-RestMethod "$api/courses"
   Invoke-RestMethod "$api/courses/$awsCourseId"
   ```

   Nêu rõ chỉ course `PUBLISHED` được trả về cho endpoint public.
2. Với student đã enrollment, lấy structure course:

   ```powershell
   $sections = Invoke-RestMethod "$api/courses/$awsCourseId/sections" -Headers $studentHeaders
   $sectionId = $sections[0].id
   $lessons = Invoke-RestMethod "$api/sections/$sectionId/lessons" -Headers $studentHeaders
   $lessonId = $lessons[0].id
   Invoke-RestMethod "$api/lessons/$lessonId" -Headers $studentHeaders
   ```

   Kỳ vọng: trả về section/lesson của course AWS. Giải thích rằng server nhận
   danh tính demo từ header và kiểm tra course đã publish/enrollment trước khi
   trả lesson.

## 3. Instructor tạo nội dung nháp — 2 phút

Tạo course nháp, section và lesson bằng instructor. Đây là phần authoring đã
có route; course mới vẫn là `DRAFT` vì repository chưa có endpoint publish.

```powershell
$courseBody = @{
  title = "Demo course $(Get-Date -Format 'HHmmss')"
  description = "Course created during the local demo"
  learning_objectives = @("Create a course", "Create a lesson")
} | ConvertTo-Json

$newCourse = Invoke-RestMethod "$api/courses" -Method Post -Headers $instructorHeaders -ContentType "application/json" -Body $courseBody

$sectionBody = @{ title = "Demo section"; position = 1 } | ConvertTo-Json
$newSection = Invoke-RestMethod "$api/courses/$($newCourse.id)/sections" -Method Post -Headers $instructorHeaders -ContentType "application/json" -Body $sectionBody

$lessonBody = @{ title = "Demo lesson"; position = 1 } | ConvertTo-Json
$newLesson = Invoke-RestMethod "$api/sections/$($newSection.id)/lessons" -Method Post -Headers $instructorHeaders -ContentType "application/json" -Body $lessonBody

$newCourse
$newSection
$newLesson
```

Kỳ vọng: ba response chứa ID, title và position tương ứng. Có thể sửa metadata
course để minh họa ownership:

```powershell
$updateBody = @{ description = "Updated during local demo" } | ConvertTo-Json
Invoke-RestMethod "$api/courses/$($newCourse.id)" -Method Patch -Headers $instructorHeaders -ContentType "application/json" -Body $updateBody
```

## 4. Kiểm tra một guardrail — 45 giây

Dùng student thử tạo course. Kết quả kỳ vọng là `403 Instructor role required`:

```powershell
try {
  Invoke-RestMethod "$api/courses" -Method Post -Headers $studentHeaders -ContentType "application/json" -Body $courseBody
} catch {
  $_.Exception.Message
}
```

Sau đó gọi enroll vào course AWS; vì seed đã enrollment cho student này,
kết quả kỳ vọng là `409 Already enrolled`. Điều này cho thấy database bảo vệ
unique enrollment và service trả xung đột rõ ràng.

```powershell
try {
  Invoke-RestMethod "$api/courses/$awsCourseId/enroll" -Method Post -Headers $studentHeaders
} catch {
  $_.Exception.Message
}
```

## 5. Kết thúc và các việc chưa demo — 30 giây

Tóm tắt phần đã xác minh: health, public course browsing, đọc lesson đã
enrollment, authoring cơ bản và role guardrail. Nêu minh bạch các bước còn
thiếu trước demo MVP đầy đủ:

- publish/review nội dung AI và trạng thái pipeline;
- progress, quiz, unlock và Tutor;
- test tự động end-to-end;
- xác thực production thay cho `X-Demo-User`;
- workflow AWS/monitoring/rollback đã kiểm chứng.

Không trình diễn upload S3 nếu không có bucket/credential test đã được review;
presigned URL còn hiệu lực là dữ liệu nhạy cảm và không nên chiếu/chia sẻ.

## Khôi phục sau demo

Course/section/lesson tạo trong bước 3 nằm trong database local. Để đưa dữ liệu
trở lại baseline, làm theo mục “Reset database local” của
[local setup](local-setup.md#7-reset-database-local). Lệnh này xóa toàn bộ
volume local, chỉ sử dụng khi không cần giữ dữ liệu demo vừa tạo.
