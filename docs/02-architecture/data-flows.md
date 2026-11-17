# Luồng dữ liệu

Tài liệu này theo dõi dữ liệu qua hai luồng cốt lõi: video → học liệu và enrollment → checkpoint → remediation. Luồng được ghi theo source hiện tại, kèm khác biệt so với báo cáo.

## Video đến học liệu

```mermaid
sequenceDiagram
    participant I as Instructor Web
    participant API as FastAPI
    participant DB as PostgreSQL
    participant S3 as S3 raw/processed
    participant EB as EventBridge
    participant SF as Step Functions
    participant K4 as Video worker
    participant K5 as AI worker

    I->>API: POST /lessons/{id}/upload-url
    API->>DB: lock + create/reuse upload intent
    API-->>I: presigned PUT + upload_id
    I->>S3: PUT immutable key
    par Xác nhận phía người dùng
      I->>API: POST /lessons/{id}/confirm-upload
      API->>S3: HeadObject + validate metadata
      API->>DB: attach raw_video_key
    and Dispatcher khi pipeline bật
      S3->>EB: Object Created
      EB->>SF: bucket/key/etag
      SF->>K4: claim + MediaConvert + verify
      K4->>DB: ledger/status/output key
      SF->>K5: Transcribe + Bedrock
      K5->>DB: transcript + draft content
      SF->>K4: finalize proof
      K4->>DB: REVIEW_REQUIRED
    end
    I->>API: GET/PATCH review draft
    I->>API: approve lesson và publish course
```

### Hợp đồng upload

- Chỉ Instructor sở hữu lesson trống trong course `DRAFT` được xin URL.
- Loại tệp cho phép: `.mp4`, `.webm`, `.mov` với Content-Type tương ứng; giới hạn 500 MiB trong service.
- Key có dạng `lessons/{lesson_id}/raw/{upload_id}.{ext}`; không dùng tên file người dùng làm identity.
- Intent được ghi trước khi trả URL; re-sign dùng lại cùng key. PUT dùng `If-None-Match: *` để không ghi đè.
- `confirm-upload` chỉ xác minh và gắn metadata. Comment/source ghi EventBridge là dispatcher initial duy nhất khi pipeline bật; điều này ngăn workflow chạy hai lần từ confirm và S3 event.

Báo cáo mô tả không dùng confirm-upload để kích hoạt. Source hiện tại vẫn giữ nguyên nguyên tắc đó, nhưng bổ sung endpoint xác nhận bền vững và frontend coi xác nhận là bước bắt buộc trước khi báo upload thành công.

### Tin cậy, retry và lỗi

| Tình huống | Cơ chế source | Kết quả an toàn |
|---|---|---|
| Event giao trùng | Claim + ledger/run identity theo upload/attempt | `IGNORE`, không tạo job mới |
| Metadata không khớp | HEAD đối chiếu key, size, type, ETag, time | Từ chối claim/confirm |
| MediaConvert submit timeout | Không auto-retry submit | Điều tra ledger/job trước khi redrive |
| Poll tạm thời lỗi | Retry hữu hạn + backoff | Tiếp tục hoặc `RecordFailure` |
| Transcribe/AI timeout | Poll bound, Catch | `FAILED`, log/ledger safe code |
| Callback run cũ | Owner/generation/raw identity check | Không ghi đè output mới |
| AI tắt | Workflow dừng ở `VIDEO_READY`, lesson còn processing | Không giả mạo approval |
| AI output sai schema/proof | Validate trước finalize | Không chuyển `REVIEW_REQUIRED` |

## Học viên, checkpoint và Tutor

```mermaid
flowchart TD
    A[Course PUBLISHED] --> B[Student enroll]
    B --> C[Section đầu mở]
    C --> D[Học lesson + lưu progress]
    D --> E[Checkpoint đã approve]
    E --> F[Backend chấm và lưu attempt/answers]
    F -->|>=80| G[passed + mở section tiếp]
    F -->|50-79.99| H[Gợi ý ôn/Tutor; retry ngay]
    F -->|<50| I[Remediation bắt buộc]
    I --> J[Giải thích câu sai]
    J --> K[Ôn flashcard/liên quan]
    K --> L[Practice >= 2/3]
    L --> M[checkpoint_remediation đủ điều kiện]
    M --> N[Retry]
```

### Gate dữ liệu

1. Identity phải là Student `ACTIVE`.
2. Course/lesson phải có trạng thái phù hợp và Student đã enroll.
3. Các section trước có quiz phải có attempt đạt tối thiểu 80; quiz/lesson hiện tại phải được duyệt/công bố.
4. Progress được lưu với session, sequence, request id và watched ranges. Completion trong source dùng threshold 10% hiện tại; đây là giới hạn cần cấu hình lại trước production.
5. Quiz submit có request id/hash để replay cùng payload được idempotent và payload khác bị từ chối.
6. Dưới 50, retry chỉ mở khi server tìm thấy bằng chứng remediation của đúng attempt.

## Đồng bộ danh tính

Cognito token được ánh xạ theo `sub` sang `users.cognito_sub`; local auth có các bảng identity/OTP/session riêng. Role nội bộ trong `users` là ranh giới authorization; source cố tình không tự nâng `INSTRUCTOR`/`ADMIN` chỉ từ email hoặc group không được đối soát. Quy trình có thể thất bại một phần giữa Cognito và RDS, nên cần reconciliation thay vì liên kết mù theo email.
