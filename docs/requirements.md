# LEARNCLOUD — YÊU CẦU VÀ LOGIC NGHIỆP VỤ

> **Loại tài liệu:** Business Requirements & Business Rules (MVP)  
> **Phiên bản tổng hợp:** 1.0 — 09/11/2026  
> **Đối tượng đọc:** Nhóm phát triển Frontend, Backend, AI Pipeline, AWS và tác nhân AI hỗ trợ phát triển  
> **Phạm vi:** Mô tả **hệ thống cần làm gì, ai được làm gì, dữ liệu thay đổi ra sao và những điều kiện nghiệp vụ phải được bảo đảm**. Đây **không phải** báo cáo xác nhận chức năng đã được lập trình hoặc triển khai thành công.

## 0. Nguồn tài liệu và quy ước

Tài liệu này được tổng hợp từ **ba PDF do nhóm cung cấp**, không tự bổ sung chức năng ngoài nguồn:

| Mã | Tài liệu | Vai trò |
|---|---|---|
| **[S1]** | `LearnCloud_Hoan_Thien.docx.pdf` (10 trang) | Ý tưởng sản phẩm, phạm vi MVP 5 tuần, quy trình Instructor/Student, AI Pipeline, Tutor, mô hình dữ liệu và giới hạn chi phí. |
| **[S2]** | `LearnCloud_Kien_truc_va_lo_trinh_4_tuan_v3.docx(1).pdf` (14 trang) | Phương án local-first 4 tuần, mô hình bảng PostgreSQL, API dự kiến, các quy tắc Backend và điều kiện nghiệm thu. |
| **[S3]** | `PROGRESS_NHOM2_FINAL(1).pdf` (23 trang) | Báo cáo tiến độ 1, mô tả nghiệp vụ 3 vai trò, Flashcard, quy tắc checkpoint chi tiết, 8 module M1–M8 và kiến trúc AWS K1–K6. |

**Quy ước:**

- **Yêu cầu**: chức năng/kết quả mong đợi của sản phẩm.
- **Quy tắc nghiệp vụ**: điều kiện quyết định hệ thống cho phép, từ chối hoặc chuyển trạng thái.
- **Thiết kế tham chiếu**: bảng/API/dịch vụ nêu trong PDF; cần đối chiếu source code trước khi coi là đã tồn tại.
- **Cần chốt**: PDF chưa xác định đủ hoặc các phiên bản không hoàn toàn thống nhất; không tự suy diễn thành yêu cầu chắc chắn.
- Trong toàn tài liệu, `Instructor`, `Student`, `Admin` là **vai trò người dùng LearnCloud**, không phải vai trò của thành viên phát triển hay IAM user AWS.

---

## 1. Tổng quan sản phẩm

**LearnCloud** là một hệ thống quản lý học tập (LMS) độc lập, ưu tiên nội dung video và sử dụng dịch vụ Cloud/AI để chuyển video bài giảng thành học liệu có cấu trúc. Trọng tâm là một vòng lặp hoàn chỉnh:

```text
Instructor tạo Course / Section / Lesson
    → Upload video
    → Pipeline xử lý video và sinh học liệu AI
    → Instructor kiểm tra, chỉnh sửa, phê duyệt
    → Publish nội dung
    → Student đăng ký và học theo Section
    → Làm checkpoint Quiz
        ├─ Đạt ≥ 80%: mở Section kế tiếp
        └─ Không đạt: ôn tập / AI Tutor / luyện tập / làm lại
    → Cập nhật Progress và Analytics
```

**Mục tiêu nghiệp vụ:**

1. Giảm thời gian giảng viên phải tự chép lời, tóm tắt và soạn câu hỏi cho video.
2. Giúp học viên học theo thứ tự, tra cứu transcript theo thời gian, ôn tập và tự đánh giá.
3. Chỉ rõ kiến thức học viên chưa nắm vững để AI Tutor hỗ trợ **đúng phần sai**.
4. Tách việc tải và xử lý video nặng khỏi request đồng bộ của web; có trạng thái, retry và nhật ký lỗi.

**Các phân hệ chức năng:** quản lý khóa học; xử lý nội dung AI; kiểm duyệt/phát hành; học tập/checkpoint; AI Tutor; thống kê và quản trị vận hành. [S1, tr. 1–2; S3, tr. 2, 9–11]

### 1.1. Ngoài phạm vi MVP

Không đặt mục tiêu làm payment/marketplace, diễn đàn hoặc chat cộng đồng, live streaming, native mobile, chứng chỉ, proctoring, tích hợp Moodle/LTI/SCORM, DRM, hệ thống recommendation phức tạp, AI Tutor đa mục đích, RAG/vector database quy mô lớn, hay hệ thống streaming nhiều bitrate cấp doanh nghiệp. Sử dụng trình phát HTML5/thư viện có sẵn. [S1, tr. 2; S2, tr. 1]

---

## 2. Người dùng và quyền nghiệp vụ

| Vai trò | Mục đích | Những thao tác chính |
|---|---|---|
| **Instructor — Giảng viên** | Tạo và chịu trách nhiệm nội dung giảng dạy | Quản lý course/section/lesson **của mình**; upload video; theo dõi pipeline; sửa/duyệt học liệu AI; publish; xem học viên và thống kê của khóa học mình sở hữu. |
| **Student — Học viên** | Tham gia và hoàn thành khóa học | Xem danh mục khóa học công khai; enroll; học lesson được cấp quyền; xem video/transcript/summary/flashcard; lưu tiến độ; làm quiz; xem kết quả; sử dụng AI Tutor khi chưa đạt. |
| **Admin — Quản trị viên hệ thống** | Quản lý tài khoản, vai trò và hoạt động cơ bản | Quản lý tài khoản/role; xem trạng thái xử lý, logs và vận hành. **Không mặc nhiên được sửa khóa học của mọi Instructor** nếu chưa có policy riêng. |

**Ranh giới quyền:**

- Phân quyền **phải được thực thi ở Backend**, không chỉ dựa vào việc ẩn nút trên React.
- Instructor chỉ được sửa nội dung thuộc course mình sở hữu, và chỉ xem danh sách/kết quả học viên thuộc course đó.
- Student không được gọi API quản lý course, upload/review/publish của Instructor.
- Student chỉ đọc nội dung học tập khi đáp ứng điều kiện publish, enrollment và unlock.
- Admin có chức năng quản trị tài khoản và vận hành; những ngoại lệ quyền cụ thể của Admin đối với course/retry cần quy định rõ.

Nguồn: [S3, tr. 3–4, 8–10]; [S2, tr. 6–8].

---

## 3. Yêu cầu chức năng theo phân hệ

### 3.1. M1 — Xác thực và quản lý tài khoản

| ID | Yêu cầu |
|---|---|
| **FR-AUTH-01** | Người dùng đăng nhập để hệ thống xác định danh tính và role `INSTRUCTOR`, `STUDENT` hoặc `ADMIN`. |
| **FR-AUTH-02** | Trong kiến trúc AWS đích, Cognito/OIDC cấp JWT; Web App gửi Bearer token cho các API bảo vệ. Backend phải kiểm tra danh tính/role trước khi thực hiện nghiệp vụ. |
| **FR-AUTH-03** | Admin có khả năng quản lý tài khoản và vai trò người dùng. |
| **FR-AUTH-04** | Không được coi `X-Demo-User` trong tài liệu local-first là cơ chế xác thực an toàn khi triển khai công khai. |

**Điểm cần chốt:** [S2, tr. 1] dùng tài khoản seed/header demo và **chưa tích hợp Cognito trong MVP local**; [S1, tr. 2–3] và [S3, tr. 9, 13] đặt Cognito là kiến trúc đích. Ba PDF **chưa quy định cụ thể** người dùng tự đăng ký role Instructor hay Admin tạo/duyệt tài khoản; cũng chưa quy định chi tiết chức năng xác thực email/quên mật khẩu. Không suy ra các workflow này đã tồn tại. 

### 3.2. M2 — Quản lý Course / Section / Lesson

| ID | Yêu cầu |
|---|---|
| **FR-COURSE-01** | Instructor tạo course với tên, mô tả và mục tiêu học tập; có thể có ảnh bìa. |
| **FR-COURSE-02** | Instructor tạo các section có thứ tự trong course và tạo các lesson trong mỗi section. |
| **FR-COURSE-03** | Instructor cập nhật metadata khóa học và nội dung lesson trong phạm vi sở hữu. |
| **FR-COURSE-04** | Course có vòng đời nháp/xuất bản; chức năng publish và, theo [S1], unpublish khóa học/nội dung. |
| **FR-COURSE-05** | Danh mục công khai chỉ hiển thị course đã `PUBLISHED`; học viên có thể xem phần giới thiệu/outline được phép công khai trước khi enroll. |
| **FR-COURSE-06** | Instructor xem danh sách học viên đã đăng ký và thống kê của course mình sở hữu. |

**Cấu trúc:** `Course (1) → (N) Section (1) → (N) Lesson`. Thứ tự section/lesson là một phần của nghiệp vụ học theo trình tự. [S1, tr. 3–4]; [S3, tr. 5–6]; [S2, tr. 6–7].

### 3.3. M3 — Upload và lưu trữ video

| ID | Yêu cầu |
|---|---|
| **FR-VIDEO-01** | Chỉ Instructor sở hữu lesson/course mới được xin URL upload cho lesson đó. |
| **FR-VIDEO-02** | Backend tạo **presigned URL có thời hạn**, gắn đúng lesson và khu vực lưu trữ cho phép. |
| **FR-VIDEO-03** | Trình duyệt gửi file **trực tiếp tới S3**, không chuyển toàn bộ video qua FastAPI/Lambda. |
| **FR-VIDEO-04** | Khi S3 nhận file, hệ thống kích hoạt pipeline bất đồng bộ; Instructor không cần giữ màn hình chờ. |
| **FR-VIDEO-05** | Instructor xem được trạng thái xử lý; khi `FAILED`, có cơ chế retry được kiểm quyền. |
| **FR-VIDEO-06** | Học viên xem bản video **processed** đã được publish, không phát raw video như luồng học tiêu chuẩn. |

[S1, tr. 3, 5–6, 8]; [S3, tr. 10, 14–15].

### 3.4. M4 — AI Content Pipeline

| ID | Yêu cầu |
|---|---|
| **FR-AI-01** | Sau upload, workflow chuẩn hóa/chuyển mã video (MediaConvert), rồi chuyển tiếng nói thành transcript có mốc thời gian (Transcribe). |
| **FR-AI-02** | AI sinh bản nháp `Summary`, `Key Concepts`/định nghĩa và `Quiz` dựa trên transcript. [S3] còn yêu cầu **Flashcard**. |
| **FR-AI-03** | Transcript được chia thành các chunk có thời gian bắt đầu/kết thúc; nội dung AI có khả năng truy xuất đoạn nguồn liên quan. |
| **FR-AI-04** | Câu hỏi quiz ở dạng có cấu trúc: 4 lựa chọn, đáp án đúng, giải thích và nguồn transcript (`source_chunk_id` hoặc timestamp). |
| **FR-AI-05** | AI trả nội dung theo JSON/schema xác định; Backend xác minh hợp lệ trước khi lưu. |
| **FR-AI-06** | Pipeline lưu trạng thái từng bước và kết quả vào PostgreSQL/S3; retry theo cấu hình, lỗi không thể phục hồi chuyển `FAILED` và ghi log. |

**Nguyên tắc chất lượng AI:** không để LLM tự bịa timestamp; timestamp lấy từ transcript; mọi câu hỏi cần căn cứ nguồn; AI chỉ tạo **bản nháp**, không tự động public nội dung. [S1, tr. 6–7]; [S3, tr. 10, 14–15].

### 3.5. M5 — Instructor Review và Publishing

| ID | Yêu cầu |
|---|---|
| **FR-REVIEW-01** | Khi học liệu AI tạo xong, lesson vào trạng thái chờ review (`REVIEW_REQUIRED`). |
| **FR-REVIEW-02** | Instructor sở hữu được xem transcript, summary, concepts, quiz và flashcard (theo phạm vi [S3]). |
| **FR-REVIEW-03** | Instructor được sửa, thêm/bớt và phê duyệt nội dung; cần xem nguồn/timestamp để đối chiếu câu hỏi. |
| **FR-REVIEW-04** | Backend từ chối publish lesson chưa được duyệt; Student không được thấy học liệu nháp/chưa publish như nội dung học chính thức. |
| **FR-REVIEW-05** | Khi duyệt và publish thành công, nội dung mới đủ điều kiện được phục vụ cho học viên có quyền truy cập. |

**Human-in-the-loop là yêu cầu bắt buộc**, vì AI không được giả định đúng tuyệt đối. [S1, tr. 3, 7]; [S3, tr. 6, 10–11].

### 3.6. M6 — Enrollment, học tập, Progress, Checkpoint, Flashcard

| ID | Yêu cầu |
|---|---|
| **FR-LEARN-01** | Student xem course đã publish và đăng ký học (**Enrollment**) trước khi truy cập nội dung dành cho học viên. |
| **FR-LEARN-02** | Section đầu tiên được mở cho Student đã enroll; các section sau mở theo kết quả checkpoint section trước. |
| **FR-LEARN-03** | Lesson hợp lệ gồm video, transcript tương tác có timestamp, summary và key concepts; click đoạn transcript tua video tới mốc tương ứng. |
| **FR-LEARN-04** | Hệ thống ghi nhận tiến độ theo lesson và tổng hợp phần trăm hoàn thành khóa học. |
| **FR-LEARN-05** | Cuối mỗi section có checkpoint quiz **đã được Instructor duyệt**. |
| **FR-LEARN-06** | Backend nhận câu trả lời, **tự chấm điểm** bằng đáp án lưu phía server; lưu từng lượt làm và từng câu trả lời. |
| **FR-LEARN-07** | Trước khi submit quiz, API không trả đáp án đúng; sau submit có thể trả điểm, câu đúng/sai và giải thích. |
| **FR-LEARN-08** | Backend quyết định quyền unlock; không thể vượt khóa chỉ bằng chỉnh UI, URL hay request API. |
| **FR-LEARN-09** | Student xem lịch sử điểm/lượt làm quiz của chính mình. |
| **FR-FLASH-01** | Theo báo cáo [S3], Student có thể ôn bằng flashcard hai mặt (thuật ngữ/câu hỏi ↔ định nghĩa/giải thích) và đánh dấu thẻ muốn xem lại. |

[S1, tr. 4]; [S2, tr. 6–8]; [S3, tr. 6–7, 10–11].

### 3.7. M7 — AI Tutor Remediation

| ID | Yêu cầu |
|---|---|
| **FR-TUTOR-01** | AI Tutor phục vụ **remediation khi Student chưa đạt checkpoint**, không phải chatbot hỏi mọi chủ đề. |
| **FR-TUTOR-02** | Bắt đầu từ **lượt làm quiz chưa đạt**; Backend nạp course, section, câu/topic sai và lịch sử làm lại liên quan. |
| **FR-TUTOR-03** | Tutor giải thích kiến thức sai, phân tích vì sao đáp án sai, đưa ví dụ ngắn và câu luyện tập. |
| **FR-TUTOR-04** | Tutor hỗ trợ hội thoại nhiều lượt trong phiên; lưu session/tin nhắn và dữ liệu luyện tập cần thiết. |
| **FR-TUTOR-05** | Kết quả remediation gắn với quyền làm lại checkpoint, theo ngưỡng điểm tại mục 4.6. |
| **FR-TUTOR-06** | Có giới hạn số lượt gọi/ngày theo Student hoặc phạm vi thích hợp để kiểm soát chi phí; đầu vào/đầu ra AI được kiểm soát. |

Tutor chỉ sử dụng ngữ cảnh do Backend chọn, kết hợp Bedrock/Guardrails theo kiến trúc đích; không yêu cầu Bedrock Agents hoặc RAG phức tạp cho MVP. [S1, tr. 7–8]; [S3, tr. 10, 15]; [S2, tr. 2, 7–8].

### 3.8. M8 — Analytics và quản trị vận hành

| ID | Yêu cầu |
|---|---|
| **FR-ANALYTICS-01** | Instructor xem số học viên enroll, tiến độ, điểm quiz trung bình và pass/fail theo course/section của mình. |
| **FR-ANALYTICS-02** | Hệ thống thống kê mức sử dụng AI Tutor ở mức cơ bản. |
| **FR-OPS-01** | Có log/metric để truy vết một job từ lúc upload tới `REVIEW_REQUIRED` hoặc `FAILED`. |
| **FR-OPS-02** | Ghi nhận lỗi pipeline, retry; thiết lập giám sát và cảnh báo chi phí/quota ở mức phù hợp. |
| **FR-ADMIN-01** | Admin có giao diện/chức năng quản lý tài khoản, role và quan sát trạng thái vận hành ở mức cơ bản. |

[S1, tr. 2–3, 5, 8]; [S3, tr. 3, 8, 10–16].

---

## 4. Quy tắc nghiệp vụ bắt buộc

### 4.1. Xác thực và quyền sở hữu

| ID | Điều kiện | Hệ thống phải thực hiện |
|---|---|---|
| **BR-01** | Request tới API bảo vệ thiếu danh tính xác thực hợp lệ | Từ chối, không tự gán tài khoản mặc định. |
| **BR-02** | Caller không có role theo yêu cầu API | Từ chối thao tác. |
| **BR-03** | Instructor A sửa/upload/review/publish tài nguyên thuộc course của Instructor B | Từ chối, bất kể Instructor A cùng role. |
| **BR-04** | Student tự yêu cầu chức năng quản trị/giảng viên | Từ chối tại Backend. |
| **BR-05** | Admin muốn tác động lên course không thuộc mình | Chỉ cho phép nếu có **policy ngoại lệ được chốt rõ**, không suy từ role Admin. |

### 4.2. Khả năng nhìn thấy khóa học và bài học

| ID | Điều kiện | Hệ thống phải thực hiện |
|---|---|---|
| **BR-06** | Course chưa `PUBLISHED` | Không liệt kê như khóa học công khai dành cho Student. |
| **BR-07** | Student chưa enroll | Có thể xem metadata công khai của course đã publish; không xem nội dung học yêu cầu enrollment. |
| **BR-08** | Student đã enroll nhưng section đang locked | Không cho đọc nội dung lesson/video/quiz bị khóa qua API. |
| **BR-09** | Lesson/học liệu chưa được duyệt hoặc publish | Không phục vụ như học liệu chính thức cho Student. |
| **BR-10** | Instructor sở hữu course đang ở DRAFT | Có thể xem/chỉnh sửa nội dung nháp để hoàn thiện. |

### 4.3. Video và AI Pipeline

| ID | Điều kiện | Hệ thống phải thực hiện |
|---|---|---|
| **BR-11** | Instructor hợp lệ yêu cầu upload lesson của mình | Cấp presigned URL có hạn, không cấp AWS credential cho trình duyệt. |
| **BR-12** | Video upload hoàn tất và sự kiện hợp lệ | Khởi chạy workflow bất đồng bộ và lưu processing status. |
| **BR-13** | AI output JSON sai schema hoặc thiếu dữ liệu bắt buộc | Không coi là học liệu hợp lệ để publish; xử lý lỗi/ghi nhận trạng thái phù hợp. |
| **BR-14** | LLM sinh timestamp/câu hỏi | Timestamp và nguồn phải quy chiếu transcript, không chấp nhận thông tin nguồn tự bịa. |
| **BR-15** | Một bước pipeline lỗi vượt số lần retry | Chuyển lesson sang `FAILED`, có log và cơ chế retry có kiểm quyền. |
| **BR-16** | Instructor chưa approve nội dung | Từ chối publish kể cả khi Frontend gửi request trực tiếp. |

### 4.4. Quy tắc Quiz và unlock

| ID | Điều kiện | Hệ thống phải thực hiện |
|---|---|---|
| **BR-17** | Student lấy quiz trước khi nộp | Không gửi `correct_answer` và thông tin tương đương làm lộ đáp án. |
| **BR-18** | Student submit quiz | Tính điểm ở Backend từ đáp án chuẩn, lưu attempt/answers, không dùng điểm do client tự khai. |
| **BR-19** | Checkpoint trước chưa `PASS` | Section tiếp theo tiếp tục `locked`, trừ section đầu tiên. |
| **BR-20** | Có attempt đạt ≥80% | Mở section kế tiếp cho chính Student đó; không mở cho học viên khác. |
| **BR-21** | Quiz/course chưa publish hoặc Student chưa enroll | Không cho đọc/nộp quiz chỉ vì biết ID endpoint. |

### 4.5. Trạng thái course và lesson

**Course:**

```text
DRAFT → PUBLISHED
```

- [S2, tr. 6] ghi `courses.status = DRAFT/PUBLISHED`.
- [S1, tr. 2] còn nêu tính năng **unpublish** nhưng chưa định nghĩa chính xác transition/ảnh hưởng tới enrollment đã có; phần này cần chốt trước khi code.

**Lesson/pipeline (luồng kỳ vọng):**

```text
DRAFT
  → UPLOADED
  → PROCESSING
  → TRANSCRIBING
  → AI_PROCESSING
  → REVIEW_REQUIRED
  → [APPROVED]
  → PUBLISHED

Từ các bước xử lý có thể → FAILED → retry theo policy.
```

| Trạng thái | Ý nghĩa |
|---|---|
| `DRAFT` | Lesson đang được xây dựng, chưa upload/hoàn thiện. |
| `UPLOADED` | File raw đã ghi vào nơi lưu trữ, sự kiện upload được ghi nhận. |
| `PROCESSING` | Xử lý/chuẩn hóa video bằng media workflow. |
| `TRANSCRIBING` | Sinh transcript và timestamp. |
| `AI_PROCESSING` | AI sinh học liệu nháp và quiz. |
| `REVIEW_REQUIRED` | Chờ Instructor kiểm tra/sửa/duyệt. |
| `APPROVED` | Đã được duyệt nhưng chưa publish; **xuất hiện trong [S3]**. |
| `PUBLISHED` | Nội dung được publish cho người học có quyền. |
| `FAILED` | Có lỗi vượt retry; cần ghi log và hỗ trợ xử lý lại. |

**Chưa thống nhất:** [S3, tr. 10–11] yêu cầu `REVIEW_REQUIRED → APPROVED → PUBLISHED`; bảng trạng thái ở [S1, tr. 3] và schema MVP [S2, tr. 6] **không liệt kê `APPROVED`**. Cần chốt một state machine và migration tương ứng. Không tự bỏ `APPROVED` hoặc tự thêm vào DB chỉ dựa trên tài liệu tổng hợp.

### 4.6. Bảng quyết định checkpoint — quy tắc quan trọng nhất

**Input:** điểm phần trăm `score` sau khi Backend chấm một attempt của Student.  
**Output:** `PASS`/`REVIEW`/`REMEDIATION`, trạng thái unlock và điều kiện retry.

| Điều kiện điểm | Kết quả | Unlock section tiếp? | AI Tutor | Quyền làm lại checkpoint |
|---|---|---|---|---|
| **`score >= 80%`** | **PASS** | **Có** | Không bắt buộc | Không cần remediation để unlock. |
| **`50% <= score < 80%`** | **REVIEW** | **Không** | Gợi ý học lại và Tutor; **có thể bỏ qua gợi ý** | Được làm lại ngay. |
| **`score < 50%`** | **REMEDIATION** | **Không** | Tutor giải thích câu sai + ví dụ + **practice** | **Phải hoàn thành luyện tập** trước khi retry. |

Quy tắc chi tiết về **50–79% được phép retry ngay** và **dưới 50% phải luyện tập trước retry** lấy từ **[S3, tr. 7, Bảng 1.3 và Hình 1.3]**. [S1, tr. 4] và [S2, tr. 2] mô tả ngắn hơn, không làm thay đổi chi tiết này.

**Ví dụ kiểm tra biên:**

| Score | Kỳ vọng |
|---:|---|
| 49,99% | REMEDIATION; chưa unlock; cần hoàn thành practice trước retry. |
| 50% | REVIEW; chưa unlock; có thể retry ngay. |
| 79,99% | REVIEW; chưa unlock; có thể retry ngay. |
| 80% | PASS; unlock section kế. |
| 100% | PASS; unlock section kế. |

**Cần chốt khi code:** cách làm tròn/tính phần trăm từ số câu đúng và biểu diễn kết quả `practice completed` để thực thi BR phía Backend. PDF không chốt công thức làm tròn hoặc số câu luyện tập tối thiểu.

### 4.7. Logic AI Tutor

```text
Student nộp Quiz
    → Backend lưu attempt, tính score và xác định câu sai
    → Nếu score < 80%, có thể tạo remediation session từ attempt
    → Backend chọn context: course, section, wrong questions/topics, retry history
    → AI Tutor: Explain → Clarify → Example → Practice
    → Lưu session, messages và trạng thái luyện tập
    → Student làm lại checkpoint theo policy ở mục 4.6
```

**Các điều kiện bất biến:**

- Tutor được gắn với **attempt của chính Student**, không cho đọc session/ngữ cảnh của người khác.
- Không cho Tutor trả lời ngoài phạm vi remediation như một chatbot đa năng theo mục tiêu MVP.
- Không cho Student tự khai `wrong_topics` hoặc `practice_completed` để vượt điều kiện kiểm tra nếu Backend có nguồn tính toán đáng tin cậy.
- Có giới hạn request/usage và kiểm soát nội dung AI; PDF chưa ấn định con số quota cụ thể.

[S1, tr. 4, 7–8]; [S3, tr. 7, 10–11].

---

## 5. Dữ liệu nghiệp vụ và quan hệ chính

Đây là **mô hình dữ liệu theo thiết kế [S2, tr. 6–7]**, được bổ sung liên hệ logic từ [S1] và [S3]. Không xác nhận schema PostgreSQL/RDS hiện tại đã đúng bảng hoặc đủ cột.

| Bảng/thực thể | Dữ liệu hoặc khóa liên quan | Vai trò nghiệp vụ |
|---|---|---|
| `users` | `id`, `cognito_sub`, `name`, `email`, `role` | Danh tính và role Student/Instructor/Admin. |
| `courses` | `id`, `instructor_id`, `title`, `description`, `learning_objectives`, `status` | Khóa học thuộc giảng viên, nháp hoặc đã publish. |
| `sections` | `id`, `course_id`, `title`, `position` | Chia course thành các chương/phần theo thứ tự. |
| `lessons` | `id`, `section_id`, `title`, `position`, raw/processed video key, `status`, transcript, summary, concepts | Bài học/video và trạng thái xử lý/nội dung. |
| `enrollments` | `student_id`, `course_id`, `enrolled_at` | Kiểm tra Student tham gia course. |
| `lesson_progress` | `student_id`, `lesson_id`, `watched_seconds`, `completed` | Ghi tiến độ học từng lesson. |
| `quizzes` | `section_id`, `passing_score`, `is_approved` | Checkpoint cuối section. |
| `questions` | `quiz_id`, `options_json`, `correct_answer`, `explanation`, `source_start`, `source_end` | Câu hỏi có đáp án chuẩn và nguồn. |
| `quiz_attempts` | `student_id`, `quiz_id`, `score`, `passed`, `attempt_number` | Lịch sử làm bài và dữ liệu để unlock. |
| `quiz_answers` | `attempt_id`, `question_id`, `selected_answer`, `is_correct` | Câu trả lời/câu sai để phục vụ Tutor. |
| `tutor_sessions` | `student_id`, `lesson_id`, `attempt_id` | Phiên AI Tutor gắn với lần làm chưa đạt. |
| `tutor_messages` | `session_id`, `role`, `content`, `created_at` | Lịch sử đối thoại Tutor. |

**Quan hệ và ràng buộc thiết kế:**

- `courses.instructor_id → users.id`.
- `sections.course_id → courses.id`; `lessons.section_id → sections.id`.
- `enrollments`: mỗi cặp `(student_id, course_id)` chỉ có một enrollment; `sections`: `(course_id, position)` không trùng.
- `lesson_progress`: `(student_id, lesson_id)` duy nhất.
- `quizzes.section_id → sections.id`; `questions.quiz_id → quizzes.id`.
- `quiz_attempts` gắn Student + Quiz; `quiz_answers` gắn Attempt + Question, `(attempt_id, question_id)` duy nhất.
- `tutor_sessions` gắn Student + Attempt (và lesson liên quan); `tutor_messages` gắn Session.

**Các điểm khác nhau / thiếu chi tiết cần giữ nguyên:**

- [S1, tr. 8] nêu `TranscriptChunk` là một **thực thể logic**; [S2, tr. 6] lưu transcript/key concepts trong `lessons` bằng JSONB. Hai cách này chưa chốt thành một schema duy nhất.
- [S3] có tính năng **Flashcard**, nhưng [S2] chưa nêu bảng và API lưu flashcard. Không tự đặt tên bảng như thể đã có.
- [S1, tr. 8] đề cập `tenant_id` cho multi-tenancy/Training Center; [S2, tr. 6] chưa thể hiện tenant trong bảng MVP. Đó là vấn đề phạm vi cần chốt.
- [S2] dự kiến UUID và thời gian UTC; cần kiểm tra DB/migration hiện tại trước khi sửa kiểu khóa.
- Nếu dùng Cognito, quan hệ giữa `cognito_sub` và `users` phải được quyết định nhất quán; không suy ra PostgreSQL phải lưu mật khẩu chỉ từ tên bảng.

---

## 6. Danh sách API tham chiếu từ thiết kế 4 tuần

> **Quan trọng:** Bảng dưới là **API dự kiến trong [S2, tr. 7–8]**, không phải kết quả kiểm kê endpoints đang chạy. Khi triển khai cần đối chiếu FastAPI OpenAPI/router và thống nhất contract với Frontend.

| Nhóm | API tham chiếu | Vai trò / mục tiêu |
|---|---|---|
| Health | `GET /health` | Kiểm tra Backend. |
| Course | `GET /courses`; `GET /courses/{id}` | Xem danh mục/outline được phép công khai. |
| Course | `POST /courses`; `PATCH /courses/{id}` | Instructor tạo/sửa course của mình. |
| Course | `POST /courses/{id}/publish` | Instructor publish theo quy tắc duyệt. |
| Section/Lesson | `POST /courses/{id}/sections`; `POST /sections/{id}/lessons` | Instructor tạo cấu trúc khóa học. |
| Lesson | `GET /lessons/{id}` | Student/Instructor đọc lesson theo quyền. |
| Upload | `POST /lessons/{id}/upload-url` | Instructor xin presigned URL. |
| Pipeline | `GET /lessons/{id}/processing-status`; `POST /lessons/{id}/retry` | Theo dõi/retry có kiểm quyền. |
| Review | `GET /lessons/{id}/ai-content`; `PATCH /lessons/{id}/ai-content`; `POST /lessons/{id}/approve` | Instructor xem/sửa/duyệt học liệu AI. |
| Enrollment | `POST /courses/{id}/enroll` | Student đăng ký khóa học. |
| Progress | `PUT /lessons/{id}/progress`; `GET /courses/{id}/progress` | Student lưu/xem tiến độ. |
| Quiz | `GET /sections/{id}/quiz`; `POST /quizzes/{id}/attempts` | Đọc quiz đã duyệt, submit và chấm điểm. |
| Quiz | `GET /students/me/quiz-history` | Xem lịch sử điểm của chính Student. |
| Tutor | `POST /tutor/sessions`; `POST /tutor/sessions/{id}/messages` | Tạo phiên từ attempt chưa đạt và chat remediation. |
| Analytics | `GET /instructor/courses/{id}/analytics` | Instructor xem tiến độ/điểm thuộc course của mình. |

**Chưa quy định đủ contract ở PDF:** API tạo/invite Instructor, danh sách/quản trị user Admin, đăng ký/đăng nhập Cognito, API riêng cho Flashcard, thao tác hoàn thành practice của Tutor, publish/unpublish chi tiết, công thức progress và một số hoạt động quản lý học liệu. Những mục đó cần thống nhất trước khi sinh API mới.

**Mã HTTP tham chiếu:** `400` dữ liệu sai, `401` chưa xác thực, `403` thiếu quyền/chưa unlock, `404` không tồn tại, `409` trạng thái nghiệp vụ không hợp lệ, `500` lỗi hệ thống. [S2, tr. 7].

---

## 7. Yêu cầu phi chức năng và ràng buộc Cloud có tác động đến nghiệp vụ

| ID | Yêu cầu/ràng buộc |
|---|---|
| **NFR-01** | Backend xử lý nghiệp vụ nhanh; tác vụ video/transcription/AI nặng chạy **bất đồng bộ** và có thể kiểm trạng thái. |
| **NFR-02** | Upload trực tiếp lên S3 bằng presigned URL; raw/processed storage không public; phân phối nội dung được phép qua CloudFront. |
| **NFR-03** | Tách business services khỏi AWS SDK qua adapters để phát triển local bằng mock, sau đó chuyển sang AWS. |
| **NFR-04** | Bảo vệ bằng xác thực, role, ownership, enrollment, publish và unlock tại Backend; không để client giữ credential AWS. |
| **NFR-05** | Không commit secret/access key; giám sát logs, lỗi pipeline, usage và chi phí. |
| **NFR-06** | Giới hạn demo bằng video ngắn, độ phân giải khoảng 720p, quota request AI và thời gian lưu artifacts theo chính sách tiết kiệm chi phí; không tuyên bố streaming enterprise/DRM. |
| **NFR-07** | Có thể kiểm thử local với fixtures/mock; kiểm thử end-to-end một luồng Instructor → Student và có dữ liệu dự phòng khi demo. |

**Kiến trúc đích được mô tả, không phải yêu cầu phải dùng đồng thời mọi dịch vụ ở local:** K1 React/S3/CloudFront/Cognito; K2 API Gateway + Lambda + FastAPI; K3 RDS PostgreSQL + S3; K4 EventBridge + Step Functions + MediaConvert + Transcribe + Lambda; K5 Bedrock/Guardrails; K6 CloudWatch/Budgets. [S1, tr. 5–8]; [S2, tr. 1, 14]; [S3, tr. 12–17].

---

## 8. Kịch bản nghiệm thu nghiệp vụ

Các kịch bản dưới đây xuất phát từ điều kiện nghiệm thu [S2, tr. 14] và quy trình [S1]/[S3]. Chúng là **test acceptance cần đạt**, không phải kết quả test hiện có.

| TC | Kịch bản | Kết quả mong đợi |
|---|---|---|
| **AC-01** | Instructor tạo course, section, lesson | Tạo thành công; course gắn đúng Instructor; có thứ tự section/lesson. |
| **AC-02** | Student hoặc Instructor B gọi API sửa course của Instructor A | Request bị từ chối ở Backend. |
| **AC-03** | Student xem danh mục trước enroll | Chỉ thấy course công khai đã publish; không nhận nội dung lesson bị hạn chế. |
| **AC-04** | Instructor xin URL và upload video | Browser PUT trực tiếp S3; không truyền toàn bộ file qua API backend. |
| **AC-05** | Upload thành công | Có trạng thái xử lý và workflow chạy/ghi nhận theo thiết kế. |
| **AC-06** | Pipeline AI thành công | Có transcript timestamp, summary/concepts và quiz bản nháp; các câu có nguồn kiểm tra. |
| **AC-07** | AI JSON sai schema hoặc pipeline lỗi | Không publish sai dữ liệu; có log/trạng thái lỗi, hỗ trợ retry. |
| **AC-08** | Instructor chưa approve nhưng gọi publish | Backend từ chối; Student chưa đọc được nội dung nháp. |
| **AC-09** | Instructor sửa, approve, publish nội dung hợp lệ | Student đã enroll và đủ unlock xem được bài. |
| **AC-10** | Student đọc quiz trước submit | Không lộ đáp án đúng. |
| **AC-11** | Student gửi đáp án kèm điểm tự khai | Backend bỏ qua điểm tự khai, tự chấm và lưu attempt/answers. |
| **AC-12** | Quiz score 80% | Pass, mở section tiếp theo **cho chính Student đó**. |
| **AC-13** | Quiz score 79,99% hoặc 50% | Chưa unlock; gợi ý ôn tập/Tutor; cho retry ngay. |
| **AC-14** | Quiz score 49,99% | Chưa unlock; phải hoàn thành remediation/practice mới được retry. |
| **AC-15** | Student truy cập section locked bằng URL/API trực tiếp | Backend từ chối lesson/video/quiz bị khóa. |
| **AC-16** | Student chưa enroll xin quiz hoặc nội dung bài học | Backend từ chối nội dung yêu cầu enrollment. |
| **AC-17** | Student tạo Tutor session từ attempt của người khác | Backend từ chối; không lộ lịch sử/ngữ cảnh của người khác. |
| **AC-18** | Instructor xem Analytics course khác chủ | Backend từ chối; chỉ trả dữ liệu course của mình. |
| **AC-19** | Student ôn Flashcard theo thiết kế [S3] | Xem hai mặt thẻ và đánh dấu thẻ cần xem lại; cách lưu cần chốt. |
| **AC-20** | Xem log một video sau xử lý | Có thể lần theo status/job tới `REVIEW_REQUIRED` hoặc `FAILED`. |

**Kịch bản demo tuyến tính:** Instructor tạo/mở course → upload video → xem trạng thái → review/approve/publish → Student enroll/học → fail checkpoint → Tutor/practice → retry pass ≥80% → section kế được mở → xem Analytics/CloudWatch. [S2, tr. 14]

---

## 9. Những điểm cần nhóm quyết định trước khi coi đây là đặc tả chốt

| Mã | Điểm chưa thống nhất/thiếu trong nguồn | Ảnh hưởng |
|---|---|---|
| **OPEN-01** | **Cognito hay tài khoản local demo ở MVP?** [S1]/[S3] hướng Cognito; [S2] cho phép demo header và chưa tích hợp Cognito trong MVP 4 tuần. | Auth, JWT, signup, role và kế hoạch tích hợp. |
| **OPEN-02** | **Ai được tạo tài khoản Instructor?** PDF chỉ mô tả Admin quản lý tài khoản/role, chưa nói rõ Admin invite/approve hay Instructor self-register. | API tạo giảng viên, bảo mật role. |
| **OPEN-03** | **Có trạng thái lesson `APPROVED` riêng không?** [S3] có, bảng trạng thái [S1]/[S2] chưa có. | Schema/migration, review/publish. |
| **OPEN-04** | **Flashcard bắt buộc trong MVP không?** [S3] mô tả như chức năng; [S1]/[S2] không có đủ bảng/API/contract tương ứng. | AI output, database, Frontend và nghiệm thu. |
| **OPEN-05** | **Transcript lưu riêng theo chunks hay JSONB trên lessons?** Các tài liệu nêu hai mô hình thiết kế khác nhau. | Data model, review/source mapping. |
| **OPEN-06** | **Có áp dụng `tenant_id` không?** [S1] đề xuất multi-tenancy; [S2] không đưa tenant vào schema MVP. | Phân quyền truy cập và cấu trúc dữ liệu. |
| **OPEN-07** | **Chính xác thế nào là hoàn thành practice để unlock retry khi <50%?** Chưa nêu tiêu chí/số câu, dữ liệu lưu hoặc API chốt. | Tutor, backend state và test biên. |
| **OPEN-08** | **Cách tính và làm tròn điểm quiz, tiến độ hoàn thành?** Chưa nêu thuật toán chi tiết. | Nghiệp vụ ở biên 50%/80%, analytics. |
| **OPEN-09** | **Unpublish course/lesson tác động enrollment, progress và quyền xem ra sao?** Có tên chức năng nhưng thiếu chính sách. | State transitions, API và dữ liệu học viên. |
| **OPEN-10** | **Quota AI Tutor, dung lượng video, số lần retry cụ thể bao nhiêu?** Tài liệu nêu cơ chế nhưng chỉ đưa giới hạn minh họa. | Chi phí, cấu hình và test. |
| **OPEN-11** | **Admin có ngoại lệ thao tác vào course/lesson hay chỉ quản lý user và vận hành?** Chưa chốt đầy đủ. | Guard quyền và audit log. |
| **OPEN-12** | **Yêu cầu xác thực email và quên mật khẩu?** Không có workflow chi tiết trong ba PDF; đây là tính năng cần đặc tả riêng nếu nhóm bổ sung. | Cognito configuration, UI và acceptance tests. |

**Nguyên tắc xử lý khác biệt:** Không âm thầm thay tài liệu nguồn bằng giả định, không coi dòng trong PDF là tính năng đã code, và không tự sửa schema/API hiện tại chỉ vì tên bảng hoặc endpoint ở bản kế hoạch cũ. Khi nhóm chốt một OPEN, cập nhật tài liệu này và API contract/migration tương ứng.

---

## 10. Checklist ngắn cho mỗi module khi hiện thực

- **Frontend:** Các màn hình/điều hướng phản ánh đúng role, publish, enrollment và unlock; nhưng quyền quyết định luôn ở Backend.
- **Backend:** Xác thực danh tính đáng tin, phân quyền role và ownership, tính score, lưu attempts/progress, kiểm điều kiện publish/enroll/unlock/retry.
- **AI Pipeline:** Đầu ra có schema, timestamp/source có căn cứ, lưu bản nháp để Instructor review, có trạng thái và lỗi/retry.
- **AI Tutor:** Gắn session với attempt chưa đạt, chỉ khai thác câu/topic sai, hỗ trợ practice, giữ lịch sử và giới hạn usage.
- **AWS:** Duy trì đường upload S3 → workflow bất đồng bộ → dữ liệu/học liệu; quan sát log và giới hạn chi phí.
- **Test:** Bao phủ luồng thành công, sai role/ownership, trạng thái chưa duyệt, chưa enroll, section locked, các biên 50%/80%, lỗi pipeline và không lộ đáp án.

**Kết luận:** LearnCloud được định nghĩa bởi hai chu trình liên thông: **Instructor biến video thành học liệu đã duyệt** và **Student học theo section, được đánh giá bằng checkpoint và khắc phục phần chưa đạt với AI Tutor**. Các quy tắc về quyền truy cập, review trước publish, chấm điểm server-side, unlock và điều kiện remediation phải được thực thi trong Backend — không chỉ thể hiện ở giao diện.
