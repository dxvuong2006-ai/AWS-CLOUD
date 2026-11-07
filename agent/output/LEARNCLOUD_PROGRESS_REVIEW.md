# LearnCloud — Đánh giá tiến độ và chuẩn bị kiểm kê AWS

Ngày lập: **06/11/2026**. Region chính: **ap-southeast-1**.

**Kết luận:** dự án đã có nhiều phần source backend, frontend, storage và điều phối video, nhưng chưa đủ căn cứ xác nhận ứng dụng chạy hoàn chỉnh. Có blocker import trong backend/pipeline; Cognito, AI worker, Tutor và một số màn hình/API còn thiếu. Audit trước chỉ xác minh được caller AWS, chưa xác minh tài nguyên K1–K6 vì lỗi quyền. Vì vậy chưa thể tính tỷ lệ triển khai AWS hoặc lập danh sách tài nguyên chắc chắn chưa tồn tại.

Phân công áp dụng cho báo cáo này: **Dũng — Admin + Cloud Deployment; Hùng — Frontend + Web Hosting; Tuấn — AI + Video Pipeline; Huy — Backend Code + Giám sát**. Không dùng bảng nhân sự cũ trong PDF hoặc `architecture.md`.

## 1. Nguồn đối chiếu và giới hạn bằng chứng

| Nguồn | Phạm vi sử dụng |
|---|---|
| [PROGRESS_2_AWS_FINAL.pdf](../agent/PROGRESS_2_AWS_FINAL.pdf) | Đã đọc mục **2.3, trang 29–39**, gồm Bảng 2.2, Hình 2.10–2.16 và Bảng 2.3; kiểm tra thêm xác thực trang 16–17, vòng đời trang 41, bảo mật trang 44–45 và API/quyết định trang 46–52. Số trang là số trang trong PDF |
| [Audit AWS trước](../agent/aws-audit-2026-11-06/LEARNCLOUD_AWS_AUDIT.md) và bốn JSON bằng chứng cùng thư mục | Kết quả quan sát AWS ngày 06/11/2026; không phải ảnh chụp AWS mới trong phiên này |
| [architecture.md](../architecture.md), [docs](../docs), [infrastructure](../infrastructure), backend/frontend/ai_pipeline | Ý định thiết kế, nội dung code và các phần còn thiếu; không chứng minh code đang được triển khai |

Đường dẫn audit được yêu cầu `output/aws-audit-2026-11-06/LEARNCLOUD_AWS_AUDIT.md` hiện không tồn tại. Đã dùng bản tìm thấy tại `agent/aws-audit-2026-11-06/`, không tạo lại hoặc sửa báo cáo cũ. Các liên kết tương đối bên trong audit cũ có thể không còn đúng sau khi chuyển thư mục; báo cáo này dẫn trực tiếp đến nguồn hiện có.

**Phiên đánh giá này thực hiện 0 lời gọi AWS.** Không chạy lại batch AccessDenied; không sửa source, database, AWS CLI config hoặc IAM; không deploy; không chạy ứng dụng/test có thể nạp `.env`, truy cập DB hoặc AWS. Chỉ tạo báo cáo và dùng công cụ đọc/render PDF cục bộ.

Quy ước đánh giá:

- **Có source:** đã thấy nội dung triển khai; chưa đồng nghĩa đã chạy được hoặc đã kiểm thử.
- **Theo tài liệu:** ghi nhận/hướng dẫn của tác giả, có thể là lịch sử hoặc mục tiêu.
- **AWS đã xác minh:** cần kết quả API metadata thành công, đúng account/Region/ARN.
- **Chưa xác minh:** thiếu bằng chứng hoặc AccessDenied; không suy ra tài nguyên không tồn tại.
- **Đã kiểm thử hoạt động:** cần bằng chứng chức năng riêng; không dùng mock, tên file, trạng thái `available` hay `SUCCEEDED` đơn lẻ thay thế.

## 2. Kiến trúc AWS đầy đủ theo mục 2.3

| Khối | Dịch vụ AWS chính phải có theo PDF | Cấu hình, thành phần phụ trợ và điều kiện | Nguồn PDF |
|---|---|---|---|
| **K1 — Truy cập & Xác thực** | **Amazon S3** hosting React tĩnh; **Amazon CloudFront**; **Amazon Cognito User Pool** | Bucket web private, Block Public Access, CloudFront **OAC**, HTTPS; Cognito OIDC/JWT, app client, nhóm quyền. Backend cấp quyền xem sau kiểm tra enrollment/unlock; diễn giải yêu cầu CloudFront signed URL cho video | Trang 29–32; M1 trang 16–17 |
| **K2 — Ứng dụng nghiệp vụ** | **Amazon API Gateway**; **AWS Lambda** chạy FastAPI qua **Mangum** | Cognito/JWT authorizer và Lambda proxy integration; Lambda gắn **Amazon VPC**, subnets/SG. Phương án PDF dự kiến **S3 Gateway VPC Endpoint** và **Bedrock Interface VPC Endpoint**; thêm endpoint secret provider nếu runtime gọi. **NAT Gateway là phương án thay thế**, không bắt buộc có đồng thời | Trang 32–33 |
| **K3 — Dữ liệu & Lưu trữ** | **Amazon RDS for PostgreSQL**; **Amazon S3 raw**; **Amazon S3 processed** | PDF mô tả hai bucket dữ liệu tách biệt; private subnets, SG RDS chỉ nhận TCP/5432 từ SG Lambda; **AWS Secrets Manager hoặc AWS Systems Manager Parameter Store** giữ mật khẩu. S3 private, CORS đúng web origin, encryption, **Lifecycle** dọn tệp trung gian. Processed chứa video 720p, transcript/học liệu; DB lưu key/metadata | Trang 34, 39 |
| **K4 — Xử lý bất đồng bộ** | **Amazon EventBridge**; **AWS Step Functions**; **AWS Elemental MediaConvert**; **Amazon Transcribe**; **Pipeline Lambda** | S3 Object Created → rule lọc bucket/đuôi tệp → workflow; các bước retry/timeout/Catch; pipeline Lambda trong VPC để ghi RDS; execution roles đúng integration. Job MediaConvert/Transcribe là workload, không phải yêu cầu một máy chủ thường trực | Trang 34–35, 39 |
| **K5 — AI tạo sinh** | **Amazon Bedrock**, **Amazon Bedrock Guardrails cho Tutor** | Pipeline gọi model sinh học liệu nháp; backend gọi model cho Tutor; IAM giới hạn model đã chọn. PDF yêu cầu Guardrails cho luồng Tutor nhận văn bản học viên, không bắt buộc áp cùng Guardrail cho mọi lượt sinh học liệu offline. InvokeModel/Converse là API, không phải hai dịch vụ riêng | Trang 35–36, 39 |
| **K6 — Giám sát & Chi phí** | **Amazon CloudWatch Logs, Metrics, Alarms**; **AWS Budgets** | Log/metric từ API Gateway, Lambda, Step Functions; alarm lỗi pipeline; cảnh báo ngân sách. Billing là nguồn chi phí. Không log secret, PII, token hoặc presigned URL | Trang 36–37, 39 |

**IAM** và execution roles là nền tảng xuyên K1–K6. Secrets Manager và Parameter Store là hai lựa chọn, không yêu cầu cả hai. Các endpoint phải theo đúng API thực gọi, service support và Region; không giả định chỉ endpoint S3/Bedrock là đủ cho MediaConvert, Transcribe, EventBridge hay secret provider.

**SNS** có thể dùng làm kênh cảnh báo theo repo; **SQS DLQ** có thể dùng cho vận hành. **EC2/SSM bridge** được tài liệu RDS ghi nhận như công cụ truy cập quản trị. Đây là phụ trợ có điều kiện, không phải các dịch vụ chính bổ sung của Bảng 2.2. Không có căn cứ yêu cầu thêm Route 53, WAF, ECS/EKS hoặc vector database để hoàn tất kiến trúc này.

## 3. Bảng tiến độ K1–K6

| Khối | Đã có trong source/tài liệu hiện tại | Còn thiếu hoặc chưa hoàn thiện trong source | Triển khai AWS và kiểm thử |
|---|---|---|---|
| **K1** | React/Vite, màn hình course/detail/learning; REST client có `VITE_API_URL`, Bearer token; hướng dẫn S3/CloudFront/OAC/Cognito | AuthContext rỗng; LoginPage/ProtectedRoute chưa có logic; App hardcode STUDENT. Chưa có Cognito login/refresh/claims flow được nối. Một số UI/API client upload, quiz, Tutor, admin còn khung | **Chưa xác minh** S3 frontend, CloudFront, Cognito do AccessDenied trong audit trước. Chưa có bằng chứng chức năng đăng nhập/hosting |
| **K2** | FastAPI routes auth/course/section/lesson/enrollment/upload/quiz/review, `/health`, các lớp service/repository, code phân quyền nghiệp vụ | Dependency vẫn dùng `X-Demo-User`; thiếu Cognito verification; chưa thấy Mangum/entrypoint Lambda backend; CORS chỉ localhost. Có blocker import nêu tại mục 4; progress/Tutor/analytics routes chưa triển khai | **Chưa xác minh** API/Lambda/VPC. Theo repo, API Sydney `/hello` và RDS probe là thử nghiệm riêng, không thay backend nghiệp vụ |
| **K3** | SQL schema/migrations, ledger/outbox migration `0005`; adapter S3 presign PUT/GET và HEAD; quy ước raw/processed; tài liệu private RDS/SG | Source dùng một bucket chia prefix, khác hai bucket dữ liệu trong PDF. Runtime đọc DATABASE_URL; chưa thấy tích hợp fetch DB secret theo đích PDF. Schema/grants/migrations phải đối chiếu thực tế | **Chưa xác minh** RDS/S3/SG/Lifecycle/secret provider. Audit HeadBucket trả 403; không chứng minh bucket vắng mặt hoặc thuộc account |
| **K4** | ASL graph; pipeline handler claim/submit/poll/verify/finalize/fail/reconcile; relay/recovery; MediaConvert adapter; ledger/outbox; EventBridge patterns, IAM templates, script đóng gói | ASL còn `${PIPELINE_LAMBDA_ARN}`/`${AI_WORKER_ARN}`; AI worker chưa được nối hoàn chỉnh. Transcribe adapter có Start/Get nhưng chưa thấy production caller/worker nối transcript → Bedrock → lưu output. Blocker import cũng ảnh hưởng pipeline | **Chưa xác minh** rules/workflow/Lambdas/jobs/roles do AccessDenied. Nhãn CODE READY/LOCAL TESTED/AWS NOT DEPLOYED trong README chỉ là ghi nhận của tác giả |
| **K5** | Bedrock adapter Claude 3 Haiku; processors summary/quiz/key concepts, prompt/schema/fixtures; API review thủ công gọi adapter; Transcribe adapter riêng | Tutor API/service/context builder/UI còn rỗng; chưa thấy Guardrail params trong `invoke_model`; chưa có Tutor rate limit/remediation flow hoàn chỉnh. Transcribe cho phép fallback mặc định | **Chưa xác minh** model availability/entitlement, Guardrail, inference profile hoặc inference thật. Audit: 11 AccessDenied và 1 UnknownOperationException ở ListCustomModels Singapore |
| **K6** | Backend đã gắn setup logging và RequestLoggingMiddleware; có JSON/text logging, request_id/status/duration; pipeline có run/job metadata; README mô tả log groups và alarms | Chưa thấy code phát custom metrics/dashboard backlog tự động; UI AdminMonitoring và admin/analytics client còn khung. Cần chuẩn hóa log an toàn, metric/alarms và đường cung cấp monitoring cho admin | **Chưa xác minh** log groups, retention, metrics, alarms, notification, Budgets. Logging source không chứng minh CloudWatch đã nhận log |

Audit cũ có **90 bản ghi: 2 STS thành công, 86 AccessDenied/UnauthorizedOperation, 1 HeadBucket 403, 1 UnknownOperationException**; đã đối chiếu lại các JSON cục bộ. Caller khi đó là `arn:aws:iam::697589240877:user/learncloud-backend-dev`. Đây là danh tính lịch sử đã xác minh, không phải danh tính được kiểm tra lại trong phiên này. Không mặc định user này thuộc Huy.

Chưa có tài nguyên ứng dụng K1–K6 nào được xác minh live thành công trong bộ bằng chứng đó; cũng chưa chứng minh được tài nguyên nào chắc chắn thiếu. IAM users khác, groups, attached/inline policies, trust/boundaries và bảy role được nhắc trong audit đều chưa đọc được. Không có cơ sở gán tỷ lệ hoàn thành AWS hoặc khẳng định pipeline đã chạy thật.

## 4. Blocker và sai lệch cần chốt trước triển khai

| Ưu tiên | Phát hiện và bằng chứng | Quyết định/công việc cần làm |
|---|---|---|
| **P0** | [course_service.py](../backend/app/services/course_service.py):8 và [video_pipeline_service.py](../backend/app/services/video_pipeline_service.py):18 import `validate_review_content`, nhưng [review_service.py](../backend/app/services/review_service.py) không định nghĩa/import symbol này | Huy xử lý hợp đồng import với Tuấn. Đây là blocker qua rà soát tĩnh, có khả năng ngăn load backend/pipeline; chưa import hoặc chạy test để xác nhận runtime |
| **P0** | [dependencies.py](../backend/app/dependencies.py):17–33 dùng header demo; [main.py](../backend/app/main.py):29–36 chỉ cho CORS localhost; [requirements.txt](../backend/requirements.txt) chưa có Mangum | Huy hoàn thiện Cognito claims/JWKS/sub mapping, packaging và production CORS trước bàn giao deploy |
| **P0** | [ASL](../infrastructure/step-functions/video_pipeline.asl.json):207–217 gọi placeholder AI worker. Chỉ có `lambda:invoke`, không có state Transcribe/Bedrock trực tiếp | Tuấn hoàn thiện worker và contract với Huy; Dũng bind ARN/roles sau khi source sẵn sàng. Không coi adapter Transcribe hoặc manual review là worker đã tích hợp |
| **P0** | [AuthContext](../frontend/src/context/AuthContext.jsx), [TutorPanel](../frontend/src/components/tutor/TutorPanel.jsx), backend [Tutor API](../backend/app/api/tutor.py), [progress API](../backend/app/api/progress.py), [analytics API](../backend/app/api/analytics.py) còn rỗng; tên file không chứng minh tính năng | Hùng hoàn thiện UI/client; Huy hoàn thiện API/services; Tuấn cung cấp logic AI/context theo contract mới |
| **P0** | PDF trang 34 yêu cầu hai bucket raw/processed; [S3 README](../infrastructure/s3/README.md) và config hiện dùng `learncloud-videos-mentorcloud` chia prefix | Dũng chốt topology chuẩn. Nếu giữ một bucket cần ghi nhận khác biệt, đối chiếu IAM/CORS/Lifecycle/event filter. Không tạo bucket mới chỉ vì chưa đọc được inventory |
| **P1** | PDF trang 29–30 yêu cầu CloudFront signed delivery; Hình 2.10 trang 31 lại vẽ signed/presigned GET tới S3. [s3_storage.py](../backend/app/adapters/storage/s3_storage.py):35–36 hiện ký S3 GET | Dũng/Hùng/Huy chốt đường phát video và tiêu chí nghiệm thu; OAC không thay kiểm tra enrollment/unlock |
| **P1** | Hình 2.13 trang 35 vẽ SFN gọi CreateJob/StartTranscriptionJob; Bảng 2.3 trang 39 lại giới hạn state machine role chỉ invoke Lambda. Source dùng Lambda submit/poll | Chốt integration thực tế; cấp quyền theo thành phần thật gọi API. Không tự thêm MediaConvert/Transcribe permissions cho SFN nếu worker mới là caller |
| **P0** | PDF trang 41/52 không thêm APPROVED, approve lesson → PUBLISHED; bảng API trang 48 còn ghi APPROVED/cần chốt. Source cũng không khớp: [review_repo.py](../backend/app/repositories/review_repo.py):201 đặt PUBLISHED, nhưng [course_service.py](../backend/app/services/course_service.py):102–105 yêu cầu APPROVED; [schemas/lesson.py](../backend/app/schemas/lesson.py):43 và enum vẫn khai báo APPROVED | Huy/Tuấn/Hùng thống nhất state machine/contract/schema/UI. Qua rà soát tĩnh, luồng review→publish course có thể từ chối lesson vừa duyệt; chưa chạy thử. Dũng ghi quyết định thiết kế, không tự chạy migration |
| **P1** | [RDS README](../infrastructure/rds/README.md) ghi kiểm chứng 31/10/2026 và migration 0005 đã triển khai; [pipeline setup](../docs/aws-video-pipeline-console-setup.md) còn nói migration mới chuẩn bị. [aws-deployment.md](../docs/aws-deployment.md) nói ASL rỗng nhưng graph hiện có | Cập nhật tài liệu sau xác minh độc lập; không chọn một ghi nhận mâu thuẫn làm sự thật live |

**Giới hạn nghiệm thu K4:** `DuplicateIgnored`, `VideoReadyAIPending`, `ReviewRequired` đều có thể kết thúc SFN bằng Succeed nhưng ý nghĩa khác nhau. Hai nhánh đầu chưa chứng minh AI hoàn tất. Phải kiểm tra output bền vững, đúng run/attempt/owner và trạng thái review; pipeline không tự approve/publish. S3 Object Created là trigger upload ban đầu; không thêm đường confirm-upload khởi động workflow lần hai. Outbox/retry phải có idempotency riêng.

## 5. Công việc còn lại theo bốn module mới

P0 là việc cần giải quyết trước tích hợp/triển khai; P1 là hoàn thiện và nghiệm thu sau đó. Đây là **backlog**, chưa thực hiện sửa code hay thao tác AWS trong phiên này.

### Dũng — Admin + Cloud Deployment

| Mức | Công việc | Đầu ra nghiệm thu |
|---|---|---|
| P0 | Chốt kiến trúc sau các sai lệch mục 4; xác nhận Region/API Sydney, naming, một/hai bucket dữ liệu và môi trường demo/prod | Registry gồm khối, ARN/tên, Region, owner, version, nguồn bằng chứng; không triển khai trùng |
| P0 | Xác nhận identity kiểm kê non-root và role/permission set chỉ đọc đã tồn tại; đối chiếu IAM user/group/execution-role trust/policies/boundary khi được phép | Phạm vi quan sát rõ ràng, không tự nâng quyền hoặc sửa IAM để vượt AccessDenied |
| P0 | Chuẩn bị VPC/private subnets/SG/routes/endpoints theo API runtime gọi; chốt Secrets Manager hoặc Parameter Store | Thiết kế đường Lambda→RDS và AWS APIs; SG5432 đúng nguồn; không bắt buộc thêm NAT khi endpoints đáp ứng |
| P1 | Sau inventory, triển khai/cấu hình phần thực sự thiếu của S3/OAC/CloudFront/Cognito/API/Lambda/RDS/K4; Hùng triển khai web trong phạm vi hosting đã giao | ARN/config ghi nhận được; package/handler/roles/trigger đúng; không dùng hello/probe thay business backend |
| P1 | Quản trị tài khoản ứng dụng trên Cognito, cloud IAM riêng và quy trình credential/secret; phối hợp Huy provision monitoring/Budgets | Không đưa AWS credentials lên frontend; audit role tách deploy/runtime role; ngân sách/người nhận cảnh báo được chủ account chốt |
| P1 | Điều phối nghiệm thu và cập nhật deployment checklist hiện còn trống | Bằng chứng từng khối + luồng end-to-end trong đợt được phép chạy workload riêng |

### Hùng — Frontend + Web Hosting

| Mức | Công việc | Đầu ra nghiệm thu |
|---|---|---|
| P0 | Hoàn thiện AuthContext/Login/ProtectedRoute; Cognito OIDC + PKCE, refresh/logout và role UI; bỏ identity hardcode | Token/claims đúng, xử lý 401/403/hết hạn; backend vẫn quyết định quyền tài nguyên |
| P0 | Nối API URL và clients/screens còn khung: upload, quiz, Tutor, analytics/admin theo contract Huy/Tuấn | Không lấy mock hoặc tên file làm tính năng hoàn tất; hiển thị lỗi thật |
| P1 | Build và deploy web vào bucket frontend đã xác minh; phối hợp Dũng CloudFront/OAC/HTTPS/SPA fallback, callback/logout/CORS | Hosting/refresh route hoạt động; S3 private; đúng endpoint/callback theo môi trường |
| P1 | Upload thẳng S3 bằng presigned PUT/required headers; theo dõi processing; review/checkpoint/Tutor; playback theo phương án đã chốt | Không gửi video lớn qua backend, không trigger workflow kép, không phát nội dung chưa được quyền |
| P1 | Xây UI giám sát/admin nếu nằm trong demo, dùng API do Huy cung cấp | Không gắn AWS key/billing credentials vào trình duyệt; chỉ hiển thị metric/status được cấp quyền |

### Tuấn — AI + Video Pipeline

| Mức | Công việc | Đầu ra nghiệm thu |
|---|---|---|
| P0 | Hoàn thiện AI worker `{run_id, execution_arn}` và contract proof/output với Huy; giải quyết validation import | Worker thật có owner/attempt/idempotency, ghi output rồi mới báo completed |
| P0 | Nối MediaConvert COMPLETE/HEAD → Transcribe start/poll/timeout → transcript timestamp → Bedrock → schema validation → lưu S3/DB | Không coi adapter rời rạc/manual review/mock là pipeline end-to-end |
| P1 | Chốt model/Region/quota/entitlement; Tutor Guardrail ID/version; tắt fallback khi nghiệm thu thật | Model đúng IAM scope; Tutor áp Guardrail; nội dung không chứa PII không cần thiết |
| P1 | Hoàn thiện Tutor context/remediation/practice và giao contract cho backend/frontend | Tutor dựa trên attempt của đúng học viên và học liệu đã duyệt; rate limit, nhánh lỗi, review gate rõ ràng |
| P1 | Kiểm tra retry/dedup/recovery/timeout và ba kết thúc Succeed; cung cấp run/job/stage telemetry cho Huy | Không job trùng, không bỏ qua AI hoặc tự publish; lỗi tra được bằng metadata không nhạy cảm |

### Huy — Backend Code + Giám sát

| Mức | Công việc | Đầu ra nghiệm thu |
|---|---|---|
| P0 | Giải quyết blocker import và xác minh khả năng khởi động/đóng gói trước deploy; thêm handler/Mangum | Artifact backend và pipeline import được trong kiểm thử được phép riêng |
| P0 | Thay `X-Demo-User`, xác minh JWT/issuer/audience hoặc client_id/token_use/expiry theo loại token; map `sub`→user; giữ role/ownership/enrollment/unlock | Không đổi danh tính bằng header; Cognito authorizer và backend trust contract thống nhất |
| P0 | Hoàn thiện progress/Tutor/analytics/admin monitoring APIs/services và contract còn thiếu; cấu hình CORS production | Endpoint thực có logic, đăng ký router và không lộ đáp án/dữ liệu vượt quyền |
| P1 | Hoàn thiện runtime secret loading; đối chiếu schema/migrations/DB grants với Dũng; giữ upload-intent/outbox/retry và review/publish đúng trạng thái | Không có mật khẩu trong source/log/env plaintext; không coi file SQL là migration đã chạy; mọi migration thực hiện theo đợt riêng |
| P1 | Chuẩn hóa structured logging, request/run/job correlation, loại token/PII/presigned URL/body/transcript/prompt; kiểm tra lỗi không log credential | Thiết kế logging có test an toàn; không chỉ có middleware mà thiếu redaction/error contract |
| P1 | **Chủ trì giám sát K6:** định nghĩa API5xx/latency, Lambda Errors/Throttles/Duration, SFN failed/timedout/aborted, EventBridge failures, pipeline backlog/stuck-run và RDS metrics cần dùng | Metric dimensions/ngưỡng/retention/dashboard/runbook được chốt; Tuấn cung cấp pipeline telemetry, Dũng provision cloud |
| P1 | Phối hợp Dũng đối chiếu alarm actions/notification và Budgets; cung cấp monitoring API an toàn cho Hùng | Chứng cứ tồn tại/cấu hình tách chứng cứ cảnh báo hoạt động; không dùng alarm OK thay kiểm thử delivery |

## 6. Những thông tin còn phải xác minh trên AWS

| Phạm vi | Thông tin/bằng chứng cần lấy khi có danh tính kiểm kê phù hợp |
|---|---|
| Toàn account | Caller/account/role mới; Region được bật; registry tags/naming; vùng nào đã kiểm tra/vùng nào ngoài phạm vi. Không kết luận global absence từ Singapore |
| K1 | Bucket frontend, location/owner/public access/encryption/policy/OAC; distribution ID/status/origin/behaviors/HTTPS/SPA; Cognito pool/app client/group/authorizer issuer; callback/logout được chủ tài nguyên cung cấp dưới dạng đã loại secret |
| K2 | API REST hay HTTP, routes/integrations/authorizer/stage; function ARN/version/handler/runtime/VPC/SG/execution role qua bằng chứng cấu hình an toàn; endpoints/NAT/routes/private DNS. Tách hello/probe khỏi backend nghiệp vụ |
| K3 | RDS identifier/engine/status/private/encryption/backups/subnets/SG; bucket raw/processed hay prefixes; Lifecycle/CORS/encryption/event notification; secret-provider ARN/type/rotation metadata, không lấy value. Schema/migration/grants cần chủ DB cung cấp kết quả preflight đã loại dữ liệu, không thể xác minh chỉ bằng RDS Describe |
| K4 | Rules/event bus/pattern/targets/roles; S3 EventBridge enabled; workflow definition/integrations và ARN placeholders đã bind; Lambda relay/recovery/worker; queue/job status và execution summaries an toàn. Output/ledger end-to-end cần đợt nghiệm thu riêng |
| K5 | Region/model hoặc inference-profile ARN, entitlement/availability/quota; Guardrail ARN/version dùng cho Tutor; execution role quyền model/Guardrail; không invoke/apply để kiểm kê |
| K6 | Log groups/retention/ingestion metadata; metrics/dimensions/dashboard/alarms/actions; SNS nếu dùng; budget type/limit/notification metadata không in email; runbook và dữ liệu monitoring đã loại secrets |
| IAM | Users/groups/membership, managed/inline policy documents và versions, execution-role trust/boundaries; không đọc access keys/login profile/credential report. Đọc policy không đồng nghĩa đã tính đủ effective permissions dưới SCP/resource policy/session boundary |

Tên ứng viên **theo repo, chưa xác minh live**: `learncloud-videos-mentorcloud`, `learncloud-db`, `learncloud-rds-probe`, `learncloud-api-prod`, workflow `learncloud-video-pipeline`, Lambda `learncloud-video-pipeline/relay/recovery`, bốn rule `learncloud-video-upload/retry/recovery/relay-tick`, budget `learncloud-demo-budget`. API mẫu `learncloud-api`/`learncloud-hello`, ID `fq5w2z5s66`, nằm ở **ap-southeast-2** theo README. `us-east-1` là Bedrock fallback trong source, chưa xác minh runtime dùng vùng này.

## 7. Quyền đọc cho đợt kiểm kê sau

Đề xuất **allowlist metadata riêng**, không dùng tên profile hoặc policy managed ReadOnlyAccess làm bằng chứng bảo đảm không đọc dữ liệu. Danh sách sau là đặc tả để chủ account đối chiếu với role có sẵn; **chưa tạo/gắn policy hay yêu cầu AdministratorAccess**.

| Phạm vi | IAM actions cần đối chiếu | Giới hạn an toàn |
|---|---|---|
| Danh tính/discovery | `ec2:DescribeRegions`; tùy chọn `tag:GetResources`; STS GetCallerIdentity không cần Allow riêng | Tags bỏ sót tài nguyên untagged, không thay inventory đầy đủ; STS chỉ xác nhận caller |
| K1/K3 S3 | `s3:ListAllMyBuckets`; bucket-scoped `s3:GetBucketLocation`, `GetBucketPublicAccessBlock`, `GetBucketPolicyStatus`, `GetBucketPolicy`, `GetBucketCORS`, `GetEncryptionConfiguration`, `GetBucketOwnershipControls`, `GetBucketVersioning`, `GetBucketWebsite`, `GetBucketNotification`, `GetLifecycleConfiguration` | Chỉ bucket metadata. Không `GetObject`, object listing hoặc download. HeadBucket cần `s3:ListBucket`, chỉ bổ sung nếu thực cần và giới hạn bucket; 403 vẫn không chứng minh absence |
| K1 CloudFront | `cloudfront:ListDistributions`, `GetDistribution`, `GetDistributionConfig`, `ListOriginAccessControls`, `GetOriginAccessControl`, `ListKeyGroups`, `GetKeyGroup`, `ListPublicKeys` theo cấu hình cần đối chiếu | **Đọc distribution/config có điều kiện**, vì response có thể chứa custom-header secrets. Baseline không-secrets dùng ARN registry và bằng chứng owner đã làm sạch; không chạy các API đó mặc định khi chưa rà soát |
| K1 Cognito | `cognito-idp:ListUserPools`, `DescribeUserPool`, `ListUserPoolClients`, `GetUserPoolMfaConfig` | Không ListUsers hoặc `DescribeUserPoolClient` trong baseline: API client detail có thể trả ClientSecret; dùng client evidence đã loại secrets |
| K2 Lambda | Trên function đã biết: `lambda:GetFunctionConcurrency`, `GetPolicy`, `ListAliases`, `ListTags` | Không đưa `ListFunctions`, `GetFunction`, `GetFunctionConfiguration`, `ListVersionsByFunction` vào baseline tuyệt đối không lấy secrets. Các response có thể chứa environment, và GetFunction có URL tải code. Handler/runtime/VPC/role dùng bằng chứng owner đã làm sạch |
| K2 API Gateway | **`apigateway:GET`** cho REST và HTTP API; discovery `/restapis`, `/apis`, rồi paths cụ thể API/resources/routes/authorizers/integrations/stages | Không cấp GET mọi path, đặc biệt `/apikeys`. Stage variables, header/request mappings có thể chứa literal nhạy cảm; cấu hình đầy đủ cần rà soát trước |
| K2/K3 network | `ec2:DescribeVpcs`, `DescribeSubnets`, `DescribeSecurityGroups`, `DescribeRouteTables`, `DescribeVpcEndpoints`, `DescribeVpcEndpointServices`, `DescribeNatGateways`, `DescribeInternetGateways`, `DescribeNetworkAcls`; `DescribeInstances` nếu cần bridge | Chỉ topology, không UserData/SSM sessions/EC2 writes |
| K3 RDS | `rds:DescribeDBInstances`, `DescribeDBClusters`, `DescribeDBSubnetGroups`, `DescribeDBParameterGroups`, `DescribeDBParameters` | Không SQL, snapshot export/download hoặc đọc dữ liệu; custom parameter literal cũng phải đánh giá khi kiểm tra sâu |
| Secret provider metadata | `secretsmanager:ListSecrets`, `DescribeSecret`; tùy chọn `ListSecretVersionIds`, `GetResourcePolicy`; **`ssm:DescribeParameters`** theo prefix | Không GetSecretValue/BatchGetSecretValue; không SSM GetParameter/GetParameters/GetParametersByPath/GetParameterHistory, kể cả không decrypt. Không `kms:Decrypt` cho audit |
| K4 EventBridge/SFN | `events:ListEventBuses`, `ListRules`, `DescribeRule`, `ListTargetsByRule`; `states:ListStateMachines`, `DescribeStateMachine`, `ListExecutions` | Targets/InputTransformer có thể chứa literal nhạy cảm. DescribeStateMachine dùng ARN state machine gốc và `--included-data METADATA_ONLY`, trả definition là `{}`; đối chiếu ASL/integrations bằng bản owner cung cấp đã loại secrets. Không cấp kms:Decrypt; không DescribeExecution/GetExecutionHistory với payload; không StartExecution/PutEvents |
| K4 MediaConvert/Transcribe | `mediaconvert:ListQueues`, `GetQueue`, `ListJobTemplates` nếu template đã đánh giá; `transcribe:ListTranscriptionJobs` | Không mặc định ListJobs/GetJob MediaConvert: response có Settings/UserMetadata/input URLs. Không GetTranscriptionJob: có TranscriptFileUri. Job summaries/names cũng có thể chứa định danh; dùng bằng chứng status đã làm sạch khi cần |
| K5 Bedrock | `bedrock:ListFoundationModels`, `GetFoundationModel`, `GetFoundationModelAvailability`, `ListInferenceProfiles`, `GetInferenceProfile`, `ListGuardrails`, `GetGuardrail`; `ListCustomModels` chỉ nếu có nhu cầu | Chỉ catalogue/account configuration; custom model không phải thành phần bắt buộc. Không InvokeModel/InvokeModelWithResponseStream/ApplyGuardrail hoặc tạo subscription/agreement |
| K6 | `logs:DescribeLogGroups`, `DescribeLogStreams`; `cloudwatch:DescribeAlarms`, `ListMetrics`, `GetMetricData`, `GetMetricStatistics`; **`budgets:ViewBudget`** | Không GetLogEvents/FilterLogEvents/StartQuery/GetQueryResults. Budget API DescribeBudgets/DescribeBudget/DescribeNotificationsForBudget dùng IAM ViewBudget; không lấy subscriber emails |
| K6 SNS nếu có | `sns:ListTopics`, `GetTopicAttributes` | Chỉ ARN/policy/counters confirmed/pending; không ListSubscriptions/GetSubscriptionAttributes chứa endpoint email. Confirmed count không chứng minh đã gửi cảnh báo |
| IAM | `iam:ListUsers`, `GetUser`, `ListGroups`, `GetGroup`, `ListGroupsForUser`; `ListAttachedUserPolicies`, `ListUserPolicies`, `GetUserPolicy`; `ListAttachedGroupPolicies`, `ListGroupPolicies`, `GetGroupPolicy`; `ListRoles`, `GetRole`, `ListAttachedRolePolicies`, `ListRolePolicies`, `GetRolePolicy`; `ListPolicies`, `GetPolicy`, `ListPolicyVersions`, `GetPolicyVersion` | Scope getter vào identities/roles/policies LearnCloud khi hỗ trợ; không IAM write/PassRole/access-key APIs/credential report/login profile |

Action thiếu prefix kế thừa prefix được ghi rõ gần nhất trong cùng nhóm. `Describe`/`Get`/`List` không tự bảo đảm nội dung response an toàn. **`--query` của AWS CLI lọc ở client sau khi nhận response**, nên không bảo đảm “không truy xuất secret”. Audit trước bị denied nên chưa nhận environment/client secret; đợt mới **không được chạy nguyên manifest cũ** chỉ vì đã có quyền đọc. Xem [AWS CLI filtering](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-filter.html), [Lambda ListFunctions response](https://docs.aws.amazon.com/lambda/latest/api/API_ListFunctions.html), [Cognito client response](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_DescribeUserPoolClient.html).

Các discovery/EC2 describe actions không hỗ trợ resource restriction cần statement `Resource: "*"` riêng; các getter hỗ trợ ARN phải giới hạn đúng tài nguyên đã xác minh. Không áp `aws:RequestedRegion=ap-southeast-1` lên toàn bộ policy: IAM/global services và Budgets cần endpoint/phạm vi riêng; API Sydney và Bedrock fallback phải được đối chiếu có chủ đích. Xem [AWS RequestedRegion](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-requestedregion).

Các mapping dễ nhầm đã kiểm tra với AWS: [S3 API/IAM actions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html), [API Gateway GET](https://docs.aws.amazon.com/service-authorization/latest/reference/list_apigateway.html), [Budgets ViewBudget](https://docs.aws.amazon.com/service-authorization/latest/reference/list_budgets.html), [DescribeSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DescribeSecret.html), [DescribeParameters không trả Value](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_DescribeParameters.html), [SFN METADATA_ONLY](https://docs.aws.amazon.com/step-functions/latest/apireference/API_DescribeStateMachine.html).

## 8. Profile kiểm kê chỉ đọc đề xuất

Tên đề xuất: **`learncloud-audit-ro`**. Profile chỉ là cách chọn credentials; tính chỉ đọc đến từ role/permission set, trust, SCP/boundaries và policies thực tế. Không dùng root credentials và không tạo access key dài hạn mới.

Nếu account **đã có IAM Identity Center và permission set kiểm kê phù hợp**, mẫu cấu hình để chủ môi trường xem xét là:

```ini
[sso-session learncloud-audit-sso]
sso_start_url = <EXISTING_SSO_START_URL>
sso_region = <IDENTITY_CENTER_REGION>
sso_registration_scopes = sso:account:access

[profile learncloud-audit-ro]
sso_session = learncloud-audit-sso
sso_account_id = 697589240877
sso_role_name = <EXISTING_APPROVED_METADATA_READ_PERMISSION_SET>
region = ap-southeast-1
output = json
cli_pager =
```

Nếu chưa dùng Identity Center nhưng **đã có role audit và quyền assume role hợp lệ**, dùng phương án thay thế, không dùng đồng thời hai định nghĩa profile cùng tên:

```ini
[profile learncloud-audit-ro]
role_arn = arn:aws:iam::697589240877:role/<EXISTING_APPROVED_AUDIT_ROLE>
source_profile = <EXISTING_NON_ROOT_TEMPORARY_OR_FEDERATED_PROFILE>
role_session_name = learncloud-inventory
region = ap-southeast-1
output = json
cli_pager =
```

Các placeholder chưa xác minh tồn tại. Không ghi các mẫu này vào `.aws/config`, không login/assume role trong phiên này, không tạo role/permission set, không sửa trust hoặc tự gắn policy. Nếu prerequisite chưa có, trạng thái là **“chưa sẵn sàng kiểm kê bằng profile đề xuất”**; tên profile không giải quyết được AccessDenied. Hướng dẫn chính thức: [SSO profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html), [assume-role profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-role.html).

## 9. Trình tự tiếp theo và tiêu chí đóng việc

1. Dũng/Huy/Tuấn chốt các sai lệch mục 4; ưu tiên import, auth, worker và schema/state contract. Hùng hoàn thiện auth/UI theo contract đó.
2. Dũng xác nhận identity kiểm kê sẵn có và rà soát allowlist metadata ở mục 7; tách API có khả năng trả secrets. Không chạy lại batch cũ.
3. Trong đợt kiểm kê được phép sau này, xác minh STS trước, discovery account/Region rồi từng khối; phân trang đầy đủ, lưu ARN/Region/time/status, dừng nhánh thiếu quyền và ghi AccessDenied. Không đổi identity hoặc nâng quyền tự động.
4. Chỉ sau khi inventory xác định thiếu mới lập thay đổi cloud cụ thể. Source tồn tại → cấu hình tồn tại → chức năng hoạt động là ba mốc nghiệm thu riêng.
5. Đợt kiểm thử workload riêng dùng dữ liệu demo và xác minh login→API→DB; upload→MediaConvert→Transcribe→Bedrock→review/publish; private playback; Tutor Guardrails; telemetry và notification. Không thực hiện trong báo cáo này.

**Bàn giao:** đã đọc kiến trúc PDF, đối chiếu source/audit, lập tiến độ K1–K6, phân công mới, danh mục cần xác minh và thiết kế profile/quyền kiểm kê. AWS deployment và functional verification vẫn chưa xác minh; không có thay đổi source hoặc tài nguyên AWS.
