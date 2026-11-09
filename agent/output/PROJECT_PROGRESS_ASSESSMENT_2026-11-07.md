# LearnCloud — Đánh giá tiến độ dự án

- **Ngày đánh giá:** 07/11/2026
- **Mục tiêu:** Đối chiếu tài liệu, source hiện có và AWS inventory đã ghi nhận để đánh giá mức sẵn sàng của LearnCloud.
- **Phạm vi:** Frontend, backend, AI/video pipeline, database và AWS.
- **Kết luận chung:** Dự án đã có nhiều luồng nghiệp vụ và giao diện được triển khai trong source, nhưng hiện phù hợp hơn với **MVP local/integration đang phát triển**, chưa đủ bằng chứng để coi là sản phẩm end-to-end sẵn sàng triển khai hoặc demo production. Các khoảng trống quan trọng nhất là backend tiến độ/media, tích hợp pipeline AI thực, xác thực Cognito/triển khai backend production và nghiệm thu tích hợp trên môi trường thật.
- **Không đưa phần trăm hoàn thành:** Chưa có bộ tiêu chí định lượng thống nhất và nhiều hạng mục AWS chưa được xác minh đầy đủ.

## 1. Nguồn và giới hạn bằng chứng

Đã đối chiếu:

- `agent/input/LearnCloud_UI_Design_Spec_v3.pdf` và `agent/input/PROGRESS_2_AWS_FINAL.pdf` là tài liệu đầu vào được chỉ định. Không trích xuất được nội dung PDF trong phiên này: công cụ PDF hệ thống không có sẵn, còn Python trong virtual environment bị hệ điều hành từ chối chạy. Do đó không khẳng định đã rà soát trực tiếp nội dung của hai PDF.
- `agent/output/LEARNCLOUD_PROGRESS_REVIEW.md`, `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md` và các báo cáo frontend/auth/quiz hiện có.
- Source trong `frontend/`, `backend/`, `ai_pipeline/`, `database/`, `infrastructure/`; tài liệu tích hợp `frontend/INTEGRATION.md`, `docs/video-pipeline-migration-0005.md`, `infrastructure/step-functions/README.md`, `infrastructure/lambda/README.md`, `README.md`.

AWS được đánh giá theo inventory đã lưu tại `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md`, có mẫu metadata đầu ngày 07/11/2026. Không gọi AWS trong lần đánh giá này; inventory ghi rõ có nhiều lỗi AccessDenied và các phần cấu hình sâu bị bỏ qua. Tồn tại tài nguyên không đồng nghĩa với pipeline đã chạy thành công.

Không chạy build, test, ứng dụng hoặc truy cập database/AWS trong lần đánh giá này. Một số báo cáo trước ghi nhận kiểm tra có mục tiêu (ví dụ frontend build); đó là bằng chứng của lần chạy trước, không phải kết quả chạy lại hôm nay.

## 2. Tóm tắt theo module

| Module | Đánh giá hiện tại | Bằng chứng và khoảng trống chính |
|---|---|---|
| **Frontend** | **Đang triển khai; có nhiều luồng UI thật và mock có kiểm soát** | Có routing theo role, đăng nhập/session JWT, trang course/learning/checkpoint, account, instructor/admin, API clients và test files. `frontend/INTEGRATION.md` ghi rõ real backend còn thiếu API danh sách khóa đã đăng ký, nội dung/media đã publish, URL video và progress/viewing sessions; mock coverage không chứng minh tích hợp backend thật. Báo cáo `FRONTEND_MERGE_PARSE_FIX.md` ghi nhận build trước đó thành công sau sửa parse. |
| **Backend** | **Nhiều nghiệp vụ cốt lõi có source; tích hợp chưa khép kín** | Có FastAPI, JWT nội bộ và role guards, course/lesson/enrollment, quiz checkpoint với idempotency, review, Tutor, analytics và video pipeline ledger/service. Nhưng `backend/app/api/progress.py` rỗng, router progress không được đăng ký trong `backend/app/main.py`, nên luồng tiến độ học chưa có API backend. `main.py` đăng ký router quiz và review hai lần qua cùng hai đối tượng router; cần rà soát để tránh route trùng/OpenAPI mơ hồ. Auth là JWT do LearnCloud tự phát hành, không phải xác thực Cognito; API register/login hiện không có email verification, recovery hoặc profile/password endpoints mà frontend contract mô tả. |
| **AI/Tutor** | **Adapter và một phần nghiệp vụ đã có; tự động hóa pipeline chưa hoàn tất** | Có adapter Bedrock/Transcribe, processors/schema/prompts và backend Tutor service/API. Tuy nhiên state machine còn placeholder `${AI_WORKER_ARN}`; `infrastructure/lambda/README.md` mô tả AI worker là điểm C cần bàn giao, không gọi mock và chỉ báo hoàn tất sau khi output được lưu. Chưa có bằng chứng pipeline thật Transcribe → xử lý AI → lưu kết quả → finalize; inventory không xác nhận inference hay Guardrail Tutor hoạt động. Adapter hoặc fixture có trong repo không phải bằng chứng AI thật chạy. |
| **Video pipeline** | **Source orchestration khá sâu; migration và worker/deployment là blocker** | Có ASL, handler pipeline/relay/recovery, ledger/outbox, adapter MediaConvert và migration 0005. Tài liệu ghi rõ workflow chưa deploy; ASL còn ARN placeholder, AI tắt mặc định, migration 0005 chưa áp dụng. Inventory cũ xác nhận một số Lambda/workflow/EventBridge resources tồn tại, nhưng không xác minh cấu hình đầy đủ hoặc E2E. |
| **Database** | **Schema/migration được chuẩn bị; trạng thái DB chưa được chốt từ bằng chứng hiện có** | Có schema, seed và nhiều migrations. Tài liệu migration 0005 ghi chưa thực thi; tài liệu khác có ghi nhận kết nối RDS thành công 31/10 nhưng không xác nhận schema hiện tại đã đồng bộ với mọi migration. Có nhiều file mang số `0004` với mục đích khác nhau; cần xác nhận thứ tự/registry migration để tránh áp dụng nhầm. |
| **AWS/Cloud** | **Đã triển khai một phần hạ tầng; chưa đủ bằng chứng vận hành sản phẩm** | Inventory ngày 07/11 ghi nhận RDS, bucket video, VPC/SG/endpoints, ba Lambda video, Step Functions, EventBridge rules và log groups tại Singapore; một số tài nguyên có workflow history. Cũng ghi nhận API đích `learncloud-api-prod` không tìm thấy đúng tên ở Singapore; API thấy tại Sydney chỉ là `/hello`; nhiều cấu hình bị AccessDenied/bỏ qua. K1 hosting/auth và K2 backend nghiệp vụ chưa đủ bằng chứng; chưa xác nhận cấu hình an toàn, hoàn chỉnh hoặc end-to-end. |

## 3. Các blocker ưu tiên

### P0 — Trước khi công bố MVP tích hợp

1. **Hoàn thành API tiến độ và media thật.** Cần backend routes/contracts cho viewing sessions, lưu watched ranges, course progress, nội dung lesson đã publish và cấp URL video có kiểm tra enrollment/unlock. Nối frontend real mode vào các API này; dữ liệu mock chỉ dùng cho demo local.
2. **Khép kín pipeline AI.** Hoàn thành và đóng gói worker; chốt contract run/attempt/ownership/output; xác minh Transcribe/Bedrock thực, ghi kết quả bền vững và chỉ finalize sau kiểm tra output. Thay ARN placeholder bằng deployment config sau khi code sẵn sàng.
3. **Chốt authentication production.** Quyết định Cognito JWT authorizer/backend validation hay tiếp tục JWT nội bộ. Hiện source chỉ thể hiện JWT nội bộ; không coi đây là Cognito/OIDC. Hoàn thiện các luồng email verification/recovery/password theo contract trước khi quảng bá account flow đầy đủ.
4. **Chốt tương thích database.** Kiểm tra migration baseline và registry trên đúng DB được phép; giải quyết tên/phiên bản migrations `0004`; chỉ áp dụng `0005` sau preflight và xác nhận môi trường. Không suy ra migration đã chạy từ việc file tồn tại.
5. **Rà soát đăng ký router FastAPI.** Xóa đăng ký kép quiz/review hoặc chứng minh đây là chủ ý; đăng ký progress router khi API sẵn sàng. Sau đó kiểm tra OpenAPI/path thực tế.

### P1 — Trước khi triển khai production

- Bổ sung adapter secrets production, cấu hình CORS/origin, Mangum/entrypoint và API Gateway/Lambda mapping; inventory hiện chưa xác nhận backend sản phẩm chạy ở Region mục tiêu.
- Chốt topology bucket raw/processed/frontend theo thiết kế và cấu hình playback (S3 presigned hay CloudFront signed), lifecycle, CORS, private access và IAM tối thiểu.
- Xác minh Guardrails cho Tutor, quota/model hiện hành, logging/alarms/budgets, retention và dashboard. AWS inventory có giới hạn quyền đọc nên những mục chưa thấy phải giữ trạng thái **chưa xác minh**, không kết luận là không tồn tại.
- Chạy nghiệm thu tích hợp trên môi trường cô lập: migration, auth/role, enrollment/unlock, upload, pipeline, review/publish, playback, checkpoint và retry/idempotency. Ghi kết quả cùng môi trường, phiên bản và log an toàn.

## 4. Backlog đề xuất theo phân công dự án

| Ưu tiên | Chủ trách nhiệm theo phân công | Công việc | Tiêu chí nghiệm thu |
|---|---|---|---|
| P0 | **Huy — Backend** | Hoàn thiện progress/media APIs và xác nhận router/API contract; rà soát đăng ký router kép; quyết định cơ chế auth production; chốt migration với DB owner. | OpenAPI có đúng một route cho mỗi operation; API progress/media kiểm tra quyền ở backend; migration được xác nhận trên DB thử nghiệm; auth production có test theo role/token. |
| P0 | **Tuấn — AI/Video** | Hoàn tất worker thật và kết nối Transcribe/Bedrock/output với ledger/finalize; giữ AI tắt cho đến khi nghiệm thu. | Video thử tạo transcript và học liệu đã lưu đúng attempt; retry không ghi đè output mới; lỗi/ReviewRequired được phân biệt; không auto-approve/publish. |
| P0 | **Hùng — Frontend** | Nối UI learning/course/account với API backend hoàn chỉnh; giữ trạng thái pending/error rõ ràng trong real mode; xác nhận phiên đăng nhập và role. | Kịch bản học thật không dùng mock; progress/media/checkpoint lấy từ backend; thao tác reload/retry không tạo trạng thái giả. |
| P0/P1 | **Dũng — AWS Admin/Cloud** | Đối chiếu cấu hình sâu và chốt topology/Region/IAM/network; triển khai backend/web sau khi nhận artifact đã kiểm thử. | ARN/config/Region và quyền đọc được ghi nhận; API sản phẩm và web hosting hoạt động trong Region đã chốt; pipeline E2E có bằng chứng, không chỉ resource tồn tại. |
| P1 | **Huy + Dũng + Tuấn** | Hoàn thiện quan sát vận hành và runbook. | Alarm, ngưỡng, log retention, cảnh báo và quy trình xử lý lỗi được xác nhận; không log secret/token/presigned URL. |

## 5. Những điểm chưa giải quyết và rủi ro đánh giá

- Không trích xuất được hai PDF input trong phiên này; đối chiếu thiết kế PDF cần thực hiện lại khi có công cụ đọc PDF hoạt động. AWS report cũ có dẫn chiếu PDF nhưng không thay thế việc đọc trực tiếp cho đánh giá đầy đủ.
- AWS inventory là ảnh chụp metadata có giới hạn quyền và thời điểm; không đại diện trạng thái live cuối ngày 07/11.
- Không chạy test/build/database/AWS trong lần đánh giá này; do đó không xác nhận source đang import được hoặc các luồng runtime hoạt động. Các kết quả test trước chỉ được xem là lịch sử.
- Có khả năng tài liệu tích hợp được cập nhật trước/sau một phần source; cần rà soát lại các mục “pending” với API thực tế trước khi đóng task.

## 6. Đề xuất bước tiếp theo

1. Chốt P0 progress/media và auth/API contract giữa Huy, Hùng và Tuấn.
2. Chốt DB migration order với bản schema/database thực tế trước khi chạy migration 0005.
3. Hoàn tất AI worker và cấu hình AWS dưới quyền đúng owner, sau đó tổ chức E2E nghiệm thu trên môi trường cô lập.
4. Cập nhật `frontend/INTEGRATION.md`, AWS inventory và báo cáo tiến độ sau mỗi nghiệm thu có bằng chứng.

