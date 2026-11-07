# LEARNCLOUD -- KẾ HOẠCH TRIỂN KHAI AWS THEO KIẾN TRÚC K1--K6

**Ngày cập nhật:** 07/11/2026\
**Tình trạng hiện tại:** Đã kiểm kê AWS thực tế ngày 06/11/2026; đang
chuyển từ giai đoạn dựng nền tảng sang giai đoạn hoàn thiện, tích hợp và
nghiệm thu.\
**Region triển khai chính:** `ap-southeast-1` (Asia Pacific --
Singapore)\
**Chủ tài khoản / Super Admin:** Huy\
**Admin triển khai AWS:** Dũng\
**Phạm vi:** Hướng dẫn chung cho Huy, Dũng, Hùng và Tuấn.

------------------------------------------------------------------------

## 1. Mục đích và nguyên tắc sử dụng tài liệu

Tài liệu này thay thế hướng dẫn dựng AWS từ đầu trước đây. Kế hoạch mới
dựa trên **tài nguyên đã được kiểm kê thực tế**, vì vậy không tạo lại
những dịch vụ đã tồn tại nếu chưa có quyết định rõ ràng.

Mục tiêu là giúp cả nhóm biết:

1.  LearnCloud hiện đã có những tài nguyên AWS nào.
2.  Mỗi khối K1--K6 còn thiếu hoặc cần xác minh điều gì.
3.  Ai chịu trách nhiệm thực hiện từng phần.
4.  Triển khai theo thứ tự nào, thao tác ở đâu và kiểm tra kết quả ra
    sao.
5.  Khi thiếu quyền IAM thì báo ai và cần cung cấp thông tin gì để được
    bổ sung.

### Nguyên tắc bắt buộc

-   **Không dựng lại toàn bộ AWS từ con số 0.** RDS, S3 video, Lambda
    pipeline, Step Functions và EventBridge đã có bằng chứng tồn tại.
-   **Không coi tài nguyên tồn tại là đã hoạt động đúng.** Phải kiểm tra
    cấu hình và chạy test riêng trước khi nghiệm thu.
-   **Không suy AccessDenied thành tài nguyên không tồn tại.** Nếu thiếu
    quyền đọc, ghi rõ "chưa xác minh".
-   **Không tự ý bật các EventBridge rule đang Disabled.** Phải kiểm tra
    target, role, event pattern và luồng xử lý trước.
-   **Không đưa access key, password, JWT, private key, secret hoặc
    presigned URL vào tài liệu, Git hay chat nhóm.**
-   **Không dùng Root credentials cho Codex, script hoặc AWS CLI.** Huy
    giữ Root để quản lý tài khoản và xử lý thao tác cấp cao; công việc
    hằng ngày dùng danh tính riêng.
-   Mọi thay đổi có thể gây downtime, đổi endpoint, xóa dữ liệu hoặc
    phát sinh chi phí phải được báo Huy trước.
-   Lambda triển khai bằng ZIP theo kế hoạch hiện tại; không bắt buộc
    dùng Docker.
-   Tất cả tài nguyên mới của môi trường demo phải ưu tiên Region
    `ap-southeast-1`, trừ khi nhóm có quyết định khác.

------------------------------------------------------------------------

## 2. Tiến độ AWS hiện tại -- ảnh chụp ngày 06/11/2026

### 2.1. Kết quả kiểm kê

Codex đã chạy kiểm kê bằng role `LearnCloudAuditReadOnlyRole` đúng AWS
account `697589240877` và xuất báo cáo
`LEARNCLOUD_AWS_INVENTORY_FINAL.md`.

  Chỉ số kiểm kê                Kết quả
  --------------------------- ---------
  Bản ghi metadata                  185
  Lệnh/record thành công            116
  AccessDenied                       65
  ResourceNotFoundException           4

65 lỗi AccessDenied là giới hạn quyền quan sát, không phải bằng chứng
rằng các tài nguyên tương ứng không tồn tại. Bốn
ResourceNotFoundException chỉ áp dụng cho đúng tài nguyên/Region đã gọi.

### 2.2. Các tài nguyên đã xác minh tồn tại

  --------------------------------------------------------------------------------------
  Dịch vụ                 Tài nguyên đã xác minh            Ghi chú
  ----------------------- --------------------------------- ----------------------------
  S3                      `learncloud-videos-mentorcloud`   Bucket video tại Singapore;
                                                            chưa xác minh đầy đủ prefix
                                                            và cấu hình object

  RDS                     `learncloud-db`                   PostgreSQL 16.9,
                                                            `available`, mã hóa,
                                                            `PubliclyAccessible=false`

  Lambda                  `learncloud-video-pipeline`       Lambda điều phối video

  Lambda                  `learncloud-video-relay`          Lambda relay

  Lambda                  `learncloud-video-recovery`       Lambda recovery

  Lambda                  `learncloud-rds-probe`            Probe kết nối, không phải
                                                            Backend API

  Lambda                  `learncloud-network-probe`        Probe mạng, không phải
                                                            Backend API

  Step Functions          `learncloud-video-pipeline`       State machine loại STANDARD

  EventBridge             `learncloud-video-upload`         ENABLED

  EventBridge             `learncloud-video-retry`          DISABLED

  EventBridge             `learncloud-video-recovery`       DISABLED

  EventBridge             `learncloud-video-relay-tick`     DISABLED

  VPC                     Default VPC Singapore             Đã tồn tại; chưa đạt
                                                            topology private subnet theo
                                                            kiến trúc đích

  EC2                     EC2 bridge                        Instance đang chạy; cần xác
                                                            nhận còn cần cho quản trị DB
                                                            hay không

  VPC Endpoints           S3, MediaConvert, EventBridge     Đã xác minh tồn tại

  CloudWatch              7 Log Groups LearnCloud           Có log group pipeline; chưa
                                                            nghiệm thu
                                                            alarms/notifications
  --------------------------------------------------------------------------------------

### 2.3. Trạng thái theo K1--K6

  ---------------------------------------------------------------------------
  Khối                    Trạng thái hiện tại     Việc chính còn lại
  ----------------------- ----------------------- ---------------------------
  **K1 -- Frontend/Auth** Chưa có bằng chứng hoàn Xác minh/tạo Cognito,
                          thiện                   bucket frontend,
                                                  CloudFront/OAC; tích hợp
                                                  login và API

  **K2 -- Backend**       Chưa xác minh Backend   Hoàn thiện code, Mangum,
                          API production tại      Lambda FastAPI, API Gateway
                          Singapore               và JWT authorizer

  **K3 --                 Đã có RDS và bucket     Rà soát subnet/SG, secret,
  Database/Storage**      video                   schema/migration,
                                                  raw/processed storage

  **K4 -- Video           Đã có Lambda, Step      Kiểm tra
  Pipeline**              Functions, EventBridge  definition/targets/roles;
                                                  hoàn thiện MediaConvert,
                                                  Transcribe, AI worker và
                                                  recovery

  **K5 -- AI**            Có metadata Bedrock;    Thay model LEGACY, xác minh
                          chưa chứng minh ứng     quyền/model access,
                          dụng AI chạy            Guardrails và AI Worker

  **K6 --                 Có log groups và metric Xác minh/tạo alarms,
  Monitoring/Cost**       metadata                Budgets, notification,
                                                  retention và dashboard
  ---------------------------------------------------------------------------

**Kết luận tiến độ:** K3 và K4 có nền tảng AWS thực tế rõ nhất. K6 đã có
logging cơ bản. K1, K2 và K5 chưa đủ bằng chứng để nghiệm thu. Chưa gán
phần trăm hoàn thành tổng thể vì các khối chưa có cùng tiêu chí nghiệm
thu.

### 2.4. Các phát hiện cần nhớ

1.  **Backend API:** tại Singapore, REST API và HTTP API trả danh sách
    rỗng trong phạm vi kiểm kê. Lambda `learncloud-api-prod` không tìm
    thấy đúng tên. Tại Sydney có HTTP API `learncloud-api` với
    `GET /hello`, chưa có authorizer; đây chỉ là API mẫu, không thay
    Backend nghiệp vụ.
2.  **RDS/network:** RDS `learncloud-db` đang
    `PubliclyAccessible=false`, nhưng subnet group thuộc Default VPC;
    các subnet có route ra Internet Gateway. Điều này không đồng nghĩa
    RDS đang public, nhưng chưa khớp thiết kế private subnet riêng trong
    kiến trúc đích.
3.  **RDS Security Group:** TCP 5432 hiện cho phép từ Lambda SG và EC2
    bridge SG. Kiến trúc đích ưu tiên chỉ cho Lambda SG; cần xác nhận
    EC2 bridge còn được dùng trước khi gỡ quyền.
4.  **Video Pipeline:** có bốn execution lịch sử: 2 `SUCCEEDED`, 2
    `FAILED`. Chưa đọc payload/output và chưa chứng minh xử lý video/AI
    end-to-end.
5.  **EventBridge:** upload rule đang ENABLED; retry, recovery và
    relay-tick đang DISABLED. Không tự bật trước khi review.
6.  **Bedrock:** source đang tham chiếu
    `anthropic.claude-3-haiku-20240307-v1:0`. Metadata tại Singapore ghi
    lifecycle `LEGACY`, EOL ngày **13/11/2026 15:00 giờ Việt Nam**. Đây
    là việc P0 của Tuấn, cần xử lý trước hạn.
7.  **Guardrails:** chưa xác minh được Guardrail ứng dụng LearnCloud tại
    các Region đã kiểm tra.
8.  **Monitoring:** có 7 log groups; alarms và Budgets chưa xác minh
    được do thiếu quyền đọc. Không kết luận chúng chưa tồn tại.

Nguồn đối chiếu: `LEARNCLOUD_AWS_INVENTORY_FINAL.md`,
`LEARNCLOUD_PROGRESS_REVIEW.md`, tài liệu kiến trúc K1--K6 và source
repository. Khi số liệu trong báo cáo cũ khác inventory mới, ưu tiên
inventory mới cho trạng thái tài nguyên AWS.

------------------------------------------------------------------------

## 3. Kiến trúc mục tiêu

``` text
Giảng viên / Học viên
        |
        +---- HTTPS ----> CloudFront ----> S3 Frontend (React)
        |                         |
        |                         +------> S3 Processed Video (private origin)
        |
        +---- Cognito login ----> JWT
        |
        +---- JWT -------------> API Gateway HTTP API
                                      |
                                      v
                              Lambda FastAPI / Mangum
                                |       |        |
                                |       |        +----> Bedrock / Guardrails
                                |       |
                                |       +-------------> S3 raw / processed
                                |
                                +---------------------> RDS PostgreSQL

Browser -- presigned PUT --> S3 raw
                                |
                                v
                           EventBridge
                                |
                                v
                         Step Functions
                                |
                 +--------------+---------------+
                 |              |               |
             MediaConvert   Transcribe      AI Worker
                 |              |               |
                 +--------------+---------------+
                                |
                         Bedrock / RDS / S3
                                |
                         Review by Instructor

CloudWatch Logs / Metrics / Alarms
AWS Budgets / email alerts
```

### Quy ước dữ liệu video

-   Raw: `lessons/{lesson_id}/raw/{object_id}.mp4`
-   Processed: `lessons/{lesson_id}/processed/...`
-   AI outputs: `lessons/{lesson_id}/ai/...`
-   Frontend build: bucket frontend riêng, không dùng bucket video làm
    nơi public website.
-   Tên prefix trên là quy ước mục tiêu; trước khi áp dụng phải đối
    chiếu key thực tế trong source và bucket hiện có.

------------------------------------------------------------------------

## 4. Phân công và IAM hiện tại

### 4.1. Vai trò nhóm

  -----------------------------------------------------------------------
  Người                   Vai trò                 Trách nhiệm
  ----------------------- ----------------------- -----------------------
  **Huy**                 Chủ tài khoản / Root    Quyết định cuối cùng,
                          Account Owner / Super   quản lý tài khoản, giám
                          Admin + Backend         sát, phát triển
                                                  Backend, nghiệm thu

  **Dũng**                Admin + Cloud           IAM, VPC, RDS
                          Deployment              infrastructure,
                                                  Lambda/API deployment,
                                                  CloudFront
                                                  infrastructure,
                                                  monitoring

  **Hùng**                Frontend                React, Cognito
                                                  integration, S3
                                                  frontend, CloudFront
                                                  hosting, giao diện
                                                  upload/playback

  **Tuấn**                AI + Video Pipeline     Bedrock, Transcribe,
                                                  MediaConvert, AI
                                                  Worker, Step Functions
                                                  và EventBridge pipeline
  -----------------------------------------------------------------------

Huy là chủ tài khoản Root/Super Admin. Không tạo IAM policy cho Root.
Không nhầm Huy với IAM User `learncloud-backend-dev`; inventory chưa xác
minh user này thuộc Huy.

### 4.2. IAM đã xác minh

  ----------------------------------------------------------------------------------
  IAM User                   Group                   Policy hiện có
  -------------------------- ----------------------- -------------------------------
  `Dung`                     `learncloud-admin`,     Group admin có
                             `learncloud-backend`    `AdministratorAccess` và các
                                                     policy dịch vụ

  `Hung`                     `leanrcloud-frontend`   `CloudFrontFullAccess`

  `Tuan`                     `learncloud-ai`         `AmazonTranscribeFullAccess`,
                                                     `AmazonBedrockFullAccess`,
                                                     `CloudWatchReadOnlyAccess`

  `learncloud-backend-dev`   Không thuộc group       Có policy riêng; chưa xác minh
                                                     mapping người sử dụng
  ----------------------------------------------------------------------------------

Tên group frontend thực tế là `leanrcloud-frontend` (đánh máy nhầm). Giữ
đúng tên khi thao tác; chỉ đổi tên sau khi Dũng kiểm tra toàn bộ
membership và automation liên quan.

### 4.3. Policy bổ sung đã thống nhất để nhóm bắt đầu làm

Đây là bộ quyền khởi đầu theo quyết định của Huy. **Không coi là bộ
quyền cuối cùng**; nếu gặp AccessDenied thì gửi lỗi để Dũng/Huy bổ sung
đúng quyền cần thiết.

  --------------------------------------------------------------------------------------
  Người                   Group                   Policy bổ sung
  ----------------------- ----------------------- --------------------------------------
  Hùng                    `leanrcloud-frontend`   `AmazonS3FullAccess`

  Tuấn                    `learncloud-ai`         `AmazonS3FullAccess`;
                                                  `AWSLambda_FullAccess`;
                                                  `AWSStepFunctionsFullAccess`;
                                                  `AmazonEventBridgeFullAccess`;
                                                  `AWSElementalMediaConvertFullAccess`

  Dũng                    `learncloud-admin`      Không cần thêm; đã có
                                                  `AdministratorAccess`

  Huy                     Root                    Không gắn IAM policy
  --------------------------------------------------------------------------------------

**Trạng thái:** tên policy đã được thống nhất; cần kiểm tra trong IAM
xem đã Attach thành công hay chưa. Không ghi "đã cấp" nếu chưa có ảnh
chụp hoặc xác nhận từ Console.

**Lưu ý về độ rộng:** `AmazonS3FullAccess`, `AWSLambda_FullAccess` và
các FullAccess khác có phạm vi rộng. Nhóm chấp nhận dùng làm quyền khởi
đầu cho môi trường demo để tránh chặn tiến độ; sau khi ổn định sẽ thay
bằng policy giới hạn resource ARN/prefix. Không cấp thêm
`AdministratorAccess` cho Hùng hoặc Tuấn.

### 4.4. Cách gắn policy cho Hùng và Tuấn

Thực hiện bằng tài khoản có quyền IAM Administrator (Dũng hoặc Huy):

1.  AWS Console → IAM → User groups.
2.  Chọn `leanrcloud-frontend`.
3.  Tab **Permissions** → **Add permissions** → **Attach policies**.
4.  Tìm `AmazonS3FullAccess`, chọn và Add permissions.
5.  Quay lại User groups, chọn `learncloud-ai`.
6.  Lặp lại thao tác và chọn năm policy đã liệt kê cho Tuấn.
7.  Mở từng group, xác nhận policy xuất hiện trong danh sách attached
    policies.
8.  Báo Hùng và Tuấn đăng nhập lại/refresh session rồi kiểm tra thao tác
    thực tế.

Nếu AWS Console không tìm thấy một tên policy, không tự chọn policy gần
giống. Chụp màn hình hoặc gửi tên policy AWS hiển thị cho Dũng/Huy để
xác minh.

### 4.5. Quy trình xử lý AccessDenied

Khi thành viên gặp lỗi, gửi đủ:

-   IAM identity đang dùng (không gửi access key).
-   Tên dịch vụ và thao tác bị từ chối, ví dụ
    `lambda:UpdateFunctionCode`.
-   Region.
-   Resource ARN hoặc tên resource.
-   Toàn bộ thông báo lỗi đã loại bỏ thông tin nhạy cảm.
-   Việc đang làm và bước vừa thực hiện.

Dũng/Huy kiểm tra lỗi thuộc một trong các loại: thiếu identity policy,
resource policy, trust relationship, `iam:PassRole`, permission
boundary, SCP hoặc sai Region/resource. Sau đó bổ sung quyền cần thiết
và yêu cầu thử lại. **Không mặc định mọi AccessDenied đều được giải
quyết bằng cách gắn thêm managed policy.**

------------------------------------------------------------------------

## 5. Thứ tự triển khai tổng thể

Thực hiện theo thứ tự dưới đây để tránh frontend chờ API, API chờ
database hoặc pipeline chạy trước khi AI Worker sẵn sàng.

  -----------------------------------------------------------------------------------
                 Thứ tự Công việc               Người chính      Điều kiện chuyển
                                                                 bước
  --------------------- ----------------------- ---------------- --------------------
                      1 Xác nhận IAM và cấp     Huy/Dũng         Hùng, Tuấn truy cập
                        quyền khởi đầu                           được dịch vụ được
                                                                 giao

                      2 Chốt registry tài       Dũng             Không tạo trùng
                        nguyên, Region, naming                   resource

                      3 Rà soát RDS, VPC, S3 và Dũng + Huy       DB/network/storage
                        secrets                                  có phương án rõ

                      4 Sửa Backend và chuẩn    Huy              Source load/package
                        hóa API contract                         được

                      5 Deploy Backend Lambda + Dũng + Huy       Health/API/auth test
                        API Gateway                              đạt

                      6 Cognito + Frontend +    Hùng + Dũng      Login và gọi API
                        CloudFront                               production được

                      7 Thay model và hoàn      Tuấn             Model active, worker
                        thiện AI Worker                          có output đúng
                                                                 schema

                      8 Hoàn thiện Step         Tuấn + Dũng      Một video test chạy
                        Functions/EventBridge                    đúng đến trạng thái
                                                                 cuối

                      9 Monitoring, budget, bảo Huy + Dũng + cả  E2E checklist đạt
                        mật và nghiệm thu       nhóm             
  -----------------------------------------------------------------------------------

Không cần chờ tất cả mọi người hoàn thành mới bắt đầu. Hùng có thể hoàn
thiện UI/Cognito integration song song; Tuấn xử lý model/worker song
song; Dũng chuẩn bị hạ tầng; Huy sửa Backend contract.

------------------------------------------------------------------------

## 6. Công việc chung trước khi triển khai

### 6.1. Xác nhận account và Region

Mọi người phải xác nhận đang thao tác đúng account `697589240877` và
Region `ap-southeast-1`.

``` powershell
aws sts get-caller-identity --profile <profile-cua-ban>
aws configure get region --profile <profile-cua-ban>
```

Không dùng profile audit read-only để tạo/sửa tài nguyên. Profile
`learncloud-audit-ro` chỉ dành cho kiểm kê metadata.

### 6.2. Registry tài nguyên

Dũng duy trì một bảng dùng chung gồm:

  Trường          Nội dung
  --------------- ------------------------------------------------------
  Resource name   Tên resource chính xác
  ARN/ID          ARN hoặc ID lấy từ AWS Console/CLI
  Region          Region
  Owner           Người phụ trách
  Purpose         Mục đích
  Status          Existing / To verify / To create / Deployed / Tested
  Last checked    Ngày kiểm tra
  Notes           Phụ thuộc, rủi ro, lỗi

Trước khi bấm Create, tìm resource hiện có theo tên, Region và loại
resource. Nếu tìm thấy resource có thể tái sử dụng thì không tạo bản thứ
hai.

------------------------------------------------------------------------

## 7. K3 -- Database, VPC và S3 Storage

**Người phụ trách:** Dũng (hạ tầng), Huy (Backend/DB integration), Tuấn
(pipeline storage).

### 7.1. Rà soát RDS hiện có -- không tạo RDS mới

RDS đã xác minh:

-   Identifier: `learncloud-db`
-   Engine: PostgreSQL 16.9
-   Instance class: `db.t3.micro`
-   Status: `available`
-   Encryption: enabled
-   Publicly accessible: `false`
-   Backup retention: 1 ngày
-   Deletion protection: `false`
-   Single-AZ

Dũng thực hiện:

1.  AWS Console → RDS → Databases → `learncloud-db`.
2.  Ghi endpoint, port, engine version, VPC, subnet group, security
    groups và backup configuration vào registry. Không ghi password.
3.  Kiểm tra tab **Connectivity & security** để xác nhận SG gắn với DB.
4.  Kiểm tra **Configuration** và backup retention.
5.  Kiểm tra snapshot/backup gần nhất trước mọi thay đổi có rủi ro.
6.  Đề xuất bật deletion protection trong thời gian demo và tăng backup
    retention phù hợp (đề xuất 7 ngày, Huy duyệt trước khi thay đổi).
7.  Không đổi DB identifier hoặc xóa DB đang có.

### 7.2. Rà soát VPC và Security Groups

Hiện tại RDS nằm trong Default VPC. Subnet group có các subnet với
`MapPublicIpOnLaunch=true` và main route table có route `0.0.0.0/0` tới
Internet Gateway. RDS vẫn `PubliclyAccessible=false`, nhưng topology
chưa khớp thiết kế private subnet riêng.

Dũng thực hiện:

1.  VPC → Your VPCs → chọn VPC hiện tại; ghi VPC ID/CIDR.
2.  Subnets → xác định subnet của RDS, AZ và route table.
3.  Route tables → kiểm tra route Internet Gateway, NAT và VPC
    endpoints.
4.  Security Groups → kiểm tra inbound TCP 5432 của RDS.
5.  Xác nhận EC2 bridge còn cần cho SSM tunnel hay không.
6.  Đối chiếu với mục tiêu: RDS không public; chỉ Lambda/backend runtime
    được phép kết nối DB; không mở TCP 5432 cho `0.0.0.0/0`.

**Không xóa rule từ EC2 bridge ngay** nếu chưa xác nhận quy trình quản
trị DB thay thế. Nếu phải chuyển RDS sang dedicated private VPC, Dũng
lập phương án migration riêng: snapshot → tạo subnet group/VPC đích →
restore DB → kiểm tra dữ liệu/kết nối → đổi secret/endpoint → nghiệm thu
→ chỉ sau đó mới xem xét dọn cấu hình cũ. Huy duyệt downtime và chi phí
trước khi làm.

### 7.3. Rà soát bucket video hiện có

Bucket đã xác minh: `learncloud-videos-mentorcloud`.

Dũng/Tuấn thực hiện:

1.  S3 → Buckets → chọn bucket.
2.  Kiểm tra Region, Block Public Access, Object Ownership, encryption,
    versioning và lifecycle.
3.  Kiểm tra CORS nếu browser upload trực tiếp.
4.  Kiểm tra EventBridge notification setting và event destination.
5.  Đối chiếu prefix raw/processed/AI với source code.
6.  Không đổi tên bucket; S3 bucket không hỗ trợ rename trực tiếp.
7.  Không xóa object hoặc thay bucket policy khi chưa hiểu tác động đến
    pipeline.

Nếu dùng một bucket chia prefix, thống nhất các prefix trong code và
IAM. Nếu tách raw/processed thành nhiều bucket, cần Dũng/Huy duyệt và
cập nhật đồng bộ Lambda, Step Functions, event rules và policy.

### 7.4. Tạo bucket frontend và artifact nếu chưa có

Inventory chưa xác minh được bucket frontend riêng. Hùng phối hợp Dũng:

1.  Kiểm tra lại danh sách S3 toàn account.
2.  Nếu chưa có bucket frontend phù hợp, tạo bucket tên duy nhất toàn
    cầu, ví dụ `learncloud-web-697589240877-<suffix>`.
3.  Region `ap-southeast-1`.
4.  Giữ **Block all public access** bật.
5.  Object Ownership: Bucket owner enforced.
6.  Bật encryption.
7.  Không bật public website hosting; CloudFront dùng S3 REST origin +
    OAC.
8.  Nếu cần lưu Lambda ZIP, tạo bucket artifact riêng, private; không
    dùng bucket video làm bucket artifact.

Tên ví dụ chỉ là mẫu; phải kiểm tra tên chưa tồn tại trước khi tạo.

------------------------------------------------------------------------

## 8. K2 -- Hoàn thiện và triển khai Backend

**Người phụ trách code:** Huy.\
**Người triển khai AWS:** Dũng.

### 8.1. Sửa source trước khi deploy

Theo lần review source gần nhất, cần xử lý các blocker sau:

1.  Hai service đang import `validate_review_content` nhưng
    `review_service` chưa định nghĩa hàm này. Huy phải bổ sung
    implementation hoặc sửa import/call site thống nhất.
2.  Trạng thái review/publish chưa thống nhất: `review_repo` ghi
    `PUBLISHED`, trong khi `publish_course` yêu cầu `APPROVED`. Chốt
    contract rõ ràng, ví dụ: review duyệt → `APPROVED`; thao tác publish
    → `PUBLISHED`. Cập nhật service, repository, schema và test đồng bộ.
3.  Bỏ `X-Demo-User` khỏi môi trường AWS. Dùng Cognito JWT đã được API
    Gateway xác minh; backend đọc `sub`/claims từ request context.
4.  Kiểm tra role, ownership, enrollment và điều kiện unlock ở backend.
    Không để frontend tự quyết định quyền xem lesson.
5.  Hoàn thiện các endpoint Tutor/progress/analytics theo phạm vi MVP;
    không trả mock/fixture trong production.
6.  Thêm `mangum` vào `backend/requirements.txt`.
7.  Tạo `backend/app/lambda_handler.py`:

``` python
from mangum import Mangum
from app.main import app

handler = Mangum(app, lifespan="off")
```

8.  Cấu hình DB secret bằng Secrets Manager hoặc SSM. Không hardcode
    password trong source, ZIP hoặc Lambda environment.
9.  Xác nhận adapter S3/AWS và dependency production; fixture chỉ dùng
    cho test.
10. Chạy unit/integration tests, kiểm tra import và khởi động ứng dụng
    trước khi đóng gói.

### 8.2. Chuẩn hóa Database

Huy phối hợp Dũng:

1.  Đối chiếu SQL schema/migrations trong repository với DB đang chạy.
2.  Xác định migration nào đã áp dụng; không chạy lại schema một cách mù
    quáng.
3.  Tạo DB application user riêng, không dùng master user cho Lambda.
4.  Secret cần chứa thông tin kết nối ứng dụng; tên dự kiến
    `learncloud/prod/database` nếu chưa có secret phù hợp.
5.  Cấp quyền DB tối thiểu cho application user.
6.  Backup trước migration có thay đổi dữ liệu.
7.  Kiểm tra kết nối từ Lambda/VPC path; không đưa DB password vào tài
    liệu hoặc log.

Nếu RDS private và máy cá nhân không truy cập trực tiếp, dùng phương án
migration được Dũng duyệt (Lambda migration dùng một lần hoặc SSM tunnel
đã kiểm soát). Sau migration, thu hồi/xóa thành phần tạm nếu không còn
cần.

### 8.3. Tạo execution role cho Backend Lambda

Dũng tạo hoặc tái sử dụng role đúng mục đích, tên mục tiêu:

`learncloud-api-lambda-role`

Role cần quyền theo code thực tế:

-   CloudWatch Logs.
-   Đọc đúng DB secret.
-   VPC network interface permissions nếu Lambda gắn VPC.
-   Đọc/ghi đúng S3 bucket/prefix mà API sử dụng.
-   Invoke đúng Bedrock model nếu API Tutor được chạy trong Backend.
-   Không gắn `AdministratorAccess`.
-   Không cấp `s3:*` hoặc `bedrock:*` trên toàn account nếu không cần.

Role này là **execution role của Lambda**, khác với IAM User của
Huy/Dũng.

### 8.4. Đóng gói Lambda ZIP

Chỉ làm sau khi code đã có handler và test đạt.

Có thể dùng AWS CloudShell để tạo package Linux tương thích Python 3.12:

``` bash
mkdir -p package
python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  -r backend/requirements.txt \
  -t package

cp -r backend/app package/app
cd package
zip -r ../learncloud-api.zip .
```

Trước khi upload:

-   Không đưa `.env`, credentials, `.venv`, `__pycache__`, test data
    nhạy cảm vào ZIP.
-   Xác nhận `app/lambda_handler.py` nằm đúng vị trí.
-   Xác nhận dependency có wheel tương thích Lambda Python 3.12/x86_64.
-   Lưu ZIP trong bucket artifact private hoặc upload theo phương thức
    được Dũng chọn.

### 8.5. Tạo Backend Lambda tại Singapore

Inventory chưa tìm thấy `learncloud-api-prod` đúng tên ở Singapore. Sau
khi hoàn tất code và role:

1.  AWS Console → Lambda → Functions → Create function.
2.  Chọn **Author from scratch**.
3.  Function name: `learncloud-api-prod`.
4.  Runtime: Python 3.12; architecture: x86_64.
5.  Execution role: `learncloud-api-lambda-role`.
6.  Upload `learncloud-api.zip`.
7.  Runtime handler: `app.lambda_handler.handler`.
8.  Cấu hình VPC/subnets/SG theo phương án network đã được Dũng duyệt.
9.  Cấu hình environment variables không chứa secret plaintext, ví dụ
    tên bucket và `DATABASE_SECRET_ARN`.
10. Đặt memory/timeout theo endpoint thực tế; request API ngắn có thể
    bắt đầu ở 1024 MB và timeout 30 giây rồi điều chỉnh theo test.
11. Tạo test event HTTP API; kiểm tra `/health`.
12. Xem CloudWatch log nếu lỗi import, timeout hoặc DB connection.

Không dùng Lambda `learncloud-rds-probe` hoặc `learncloud-network-probe`
thay Backend nghiệp vụ.

### 8.6. Tạo API Gateway HTTP API

Sau khi Lambda hoạt động:

1.  API Gateway → Create API → HTTP API.
2.  API name: `learncloud-api-prod`.
3.  Thêm Lambda integration trỏ tới `learncloud-api-prod` ở
    `ap-southeast-1`.
4.  Tạo routes `ANY /` và `ANY /{proxy+}` nếu phù hợp với routing
    FastAPI.
5.  Tạo JWT authorizer:
    -   Issuer: Cognito issuer URL.
    -   Audience: Cognito App Client ID.
6.  Gán authorizer cho các route nghiệp vụ.
7.  Chỉ để `/health` public nếu cần health check.
8.  Stage `$default`, bật auto-deploy.
9.  Ghi Invoke URL vào registry.
10. Cập nhật `VITE_API_URL` cho frontend.

**Test bắt buộc:**

-   Gọi route nghiệp vụ không token → 401.
-   Token sai/hết hạn → bị từ chối.
-   Token hợp lệ → gọi được API.
-   Student không đọc draft/lesson chưa unlock.
-   Instructor không sửa course của người khác.
-   `/health` phản ánh trạng thái ứng dụng; không dùng health endpoint
    để lộ secret hoặc thông tin nội bộ.

------------------------------------------------------------------------

## 9. K1 -- Cognito, Frontend S3 và CloudFront

**Người phụ trách:** Hùng.\
**AWS infrastructure:** Dũng.\
**Backend contract/auth:** Huy.

### 9.1. Xác minh hoặc tạo Cognito User Pool

Inventory chưa tìm thấy User Pool ở Singapore và Sydney trong phạm vi đã
kiểm tra. Dũng/Hùng xác minh lại trước khi tạo.

Nếu chưa có pool phù hợp:

1.  AWS Console → Amazon Cognito → User pools → Create user pool.
2.  Sign-in bằng email.
3.  Tạo app client loại public client cho SPA; không tạo client secret.
4.  Dùng OIDC Authorization Code + PKCE.
5.  Tạo domain Cognito.
6.  Ghi User Pool ID, App Client ID, domain và issuer URL vào registry
    (không ghi secret vì SPA public client không có client secret).
7.  Tạo groups `Instructor`, `Student`, `Admin`.
8.  Tạo user demo và gán group bởi người quản trị; không cho người dùng
    tự chọn quyền Admin/Instructor qua form đăng ký.
9.  Sau khi có CloudFront domain, cập nhật callback/logout URLs đúng
    HTTPS domain.

Cognito xác minh danh tính và phát token. Backend vẫn phải kiểm tra
ownership, enrollment, role và unlock.

### 9.2. Hoàn thiện frontend

Hùng:

1.  Xác định API base URL production.
2.  Cấu hình Cognito issuer, User Pool ID, App Client ID và
    callback/logout URLs.
3.  Tích hợp login/logout/refresh theo PKCE.
4.  Gửi `Authorization: Bearer <JWT>` khi gọi API.
5.  Bỏ hardcode role `STUDENT`; role phải lấy từ claims đã xác minh và
    dữ liệu backend.
6.  Hoàn thiện AuthContext, route guard và trạng thái session.
7.  Nối các màn hình course, lesson, upload, quiz, review, progress và
    Tutor với API thật.
8.  Không dùng mock/fixture làm bằng chứng đã tích hợp production.
9.  Upload video bằng presigned URL do Backend cấp; không nhúng AWS
    access key vào trình duyệt.

### 9.3. Build React/Vite

Trên máy phát triển:

``` powershell
cd frontend
$env:VITE_API_URL = "<API_GATEWAY_INVOKE_URL>"
npm.cmd install
npm.cmd run build
```

Cấu hình Cognito theo cách dự án đang quản lý environment variables.
Không đưa secret backend vào biến `VITE_*` vì các biến này được đóng gói
vào trình duyệt.

Build phải tạo được `frontend/dist`.

### 9.4. Upload lên S3 và cấu hình CloudFront

Dũng/Hùng:

1.  Kiểm tra lại account xem đã có frontend bucket/distribution phù hợp
    chưa.
2.  Nếu chưa có bucket frontend, tạo bucket riêng ở Singapore.
3.  Giữ Block Public Access bật; không public bucket.
4.  Upload **nội dung bên trong** `frontend/dist` lên bucket.
5.  CloudFront → Distributions → Create distribution.
6.  Origin là S3 REST endpoint, không dùng public S3 website endpoint.
7.  Tạo Origin Access Control (OAC), signing behavior `Sign requests`.
8.  Viewer protocol policy: Redirect HTTP to HTTPS.
9.  Default root object: `index.html`.
10. Cập nhật bucket policy theo OAC để chỉ distribution được đọc bucket.
11. Cấu hình SPA fallback: 403/404 trả `index.html` với response code
    200 nếu phù hợp router.
12. Chờ distribution `Deployed`.
13. Ghi CloudFront domain vào registry; cập nhật Cognito callback/logout
    URLs và CORS raw bucket.
14. Khi upload bản mới, tạo invalidation `/*`.

### 9.5. Video playback bảo vệ bằng signed URL

Chỉ làm sau khi processed storage và CloudFront origin đã được xác định:

1.  Dùng CloudFront public key/key group.
2.  Tạo behavior cho path processed video.
3.  Backend kiểm tra enrollment, lesson published và unlock trước khi ký
    URL.
4.  Backend trả signed URL có thời hạn.
5.  URL không ký hoặc hết hạn phải bị từ chối.
6.  Không public bucket processed và không trả URL S3 trực tiếp cho học
    viên.
7.  Private key chỉ lưu trong Secrets Manager; không commit vào Git,
    không đưa vào frontend.

------------------------------------------------------------------------

## 10. K4 -- Hoàn thiện Video Processing Pipeline

**Người phụ trách AI/Pipeline:** Tuấn.\
**AWS deployment và IAM:** Dũng.\
**Backend state/contract:** Huy.

### 10.1. Kiểm tra tài nguyên đang có trước khi sửa

Tại Singapore đã xác minh:

-   Lambda `learncloud-video-pipeline`
-   Lambda `learncloud-video-relay`
-   Lambda `learncloud-video-recovery`
-   Step Functions `learncloud-video-pipeline`
-   EventBridge `learncloud-video-upload` (ENABLED)
-   EventBridge `learncloud-video-retry` (DISABLED)
-   EventBridge `learncloud-video-recovery` (DISABLED)
-   EventBridge `learncloud-video-relay-tick` (DISABLED)

Dũng/Tuấn cần kiểm tra:

1.  Lambda code version, runtime, handler và execution role (không
    đọc/đưa environment secrets vào báo cáo).
2.  State machine definition, logging configuration và execution role.
3.  EventBridge rule event pattern, schedule, target ARN và target role.
4.  MediaConvert queue, job role và output destination.
5.  Transcribe job configuration và output location.
6.  S3 raw bucket EventBridge notification.
7.  Các quyền `iam:PassRole` có giới hạn đúng role cần dùng.

### 10.2. Hoàn thiện workflow trong source

File `infrastructure/step-functions/video_pipeline.asl.json` được báo
cáo là placeholder/chưa có định nghĩa hoàn chỉnh. Tuấn cần hoàn thiện
ASL và handlers theo luồng:

1.  Nhận event video raw được upload.
2.  Xác định `lesson_id`, bucket, object key và execution id.
3.  Kiểm tra file/metadata hợp lệ.
4.  Tạo MediaConvert job để chuẩn hóa video và ghi output processed.
5.  Chờ MediaConvert hoàn tất; xử lý timeout/failure.
6.  Tạo Transcribe job cho video/audio phù hợp.
7.  Chờ transcription hoàn tất và lấy transcript có timestamp.
8.  Gọi AI Worker/Bedrock để tạo summary, sections, concepts,
    quiz/roadmap theo schema.
9.  Validate output; nếu không hợp lệ thì chuyển `REVIEW_REQUIRED` hoặc
    `FAILED` với lý do.
10. Ghi output bền vững vào S3 và cập nhật trạng thái/metadata trong
    RDS.
11. Instructor review; pipeline không tự publish nội dung chưa được
    duyệt.

### 10.3. Tách trách nhiệm giữa các Lambda

-   `learncloud-video-pipeline`: điều phối nghiệp vụ theo code hiện tại;
    không mặc định nó đã hoàn thành mọi task.
-   `learncloud-video-relay`: chỉ làm nhiệm vụ relay đã định nghĩa; Tuấn
    phải mô tả input/output.
-   `learncloud-video-recovery`: xử lý retry/recovery có kiểm soát,
    không tạo job trùng.
-   AI Worker: cần được xác định rõ function name/ARN; inventory chưa
    xác minh được function AI Worker riêng.

Nếu cần tạo Lambda AI Worker mới, Tuấn cung cấp handler, input/output
schema và dependency; Dũng tạo execution role và deploy sau khi review.

### 10.4. Retry, deduplication và trạng thái

Bắt buộc:

-   Chống chạy trùng theo khóa nghiệp vụ, ví dụ
    `(lesson_id, object_key)` hoặc idempotency key.
-   Có timeout và retry có giới hạn cho lỗi tạm thời.
-   Có `Catch`/error path; không chuyển thành `SUCCEEDED` khi output AI
    chưa được lưu.
-   Phân biệt `FAILED`, `RETRY_PENDING`, `PROCESSING`,
    `REVIEW_REQUIRED`, `APPROVED`, `PUBLISHED` theo contract thống nhất
    với Huy.
-   Chỉ một nguồn trigger chính: S3 Object Created/EventBridge. Không
    đồng thời khởi chạy cùng workflow từ nhiều trigger không có dedup.
-   Mỗi execution phải có log/metadata đủ để truy vết nhưng không ghi
    token, secret hoặc video payload.

### 10.5. Chỉ bật retry/recovery rules sau khi review

Không bật ba rule Disabled ngay.

Trước khi bật, Dũng và Tuấn phải xác nhận:

-   Rule pattern/schedule đúng mục đích.
-   Target đúng Lambda/State Machine.
-   Target role có quyền đúng.
-   Retry không tạo job lặp hoặc tính phí lặp.
-   Recovery có giới hạn số lần và dead-letter/failed status rõ ràng.
-   Có test video ngắn và kế hoạch rollback.

Sau khi review, bật từng rule một, kiểm thử, quan sát log/metrics rồi
mới bật rule tiếp theo.

### 10.6. Test pipeline bằng một video ngắn

1.  Dùng video demo không chứa dữ liệu cá nhân.
2.  Backend cấp presigned PUT URL đúng raw prefix.
3.  Browser upload trực tiếp lên S3 raw.
4.  Xác nhận một EventBridge event và một Step Functions execution.
5.  Kiểm tra từng task MediaConvert, Transcribe, AI Worker.
6.  Xác nhận output processed/AI được ghi vào đúng prefix.
7.  Xác nhận RDS có trạng thái và metadata đúng.
8.  Xác nhận nội dung chuyển sang `REVIEW_REQUIRED`.
9.  Instructor duyệt; Backend mới cho phép publish.
10. Lưu execution ARN, thời điểm, trạng thái và log reference vào biên
    bản nghiệm thu; không lưu payload nhạy cảm.

------------------------------------------------------------------------

## 11. K5 -- Bedrock, Model và Guardrails

**Người phụ trách:** Tuấn.\
**Hỗ trợ IAM/network:** Dũng.\
**Contract/API:** Huy.

### 11.1. Xử lý model LEGACY ngay

Source hiện tham chiếu:

`anthropic.claude-3-haiku-20240307-v1:0`

Inventory ngày 06/11 ghi model tại Singapore ở trạng thái `LEGACY`, EOL
**13/11/2026 15:00 giờ Việt Nam**.

Tuấn phải ưu tiên:

1.  Tìm tất cả vị trí source/config đang tham chiếu model ID này.
2.  AWS Console → Amazon Bedrock → Model catalog tại Region Singapore.
3.  Chọn model phù hợp với tác vụ summary, sectioning, quiz và roadmap.
4.  Kiểm tra model lifecycle còn Active, Region availability, model
    access/entitlement, agreement và quota.
5.  Kiểm tra model có hỗ trợ API/format mà code đang dùng.
6.  Chốt model ID với Huy trước khi đổi cấu hình.
7.  Cập nhật model ID qua cấu hình, không hardcode rải rác.
8.  Cập nhật IAM execution role chỉ cho model cần gọi.
9.  Chạy test prompt không chứa dữ liệu cá nhân; xác nhận JSON/schema
    đầu ra.
10. Kiểm tra chi phí và latency trên một số video demo ngắn.

Không mặc định model hiển thị `AVAILABLE` là có thể invoke thành công;
phải xác minh quyền truy cập và thực hiện test invocation có kiểm soát.
Không tự hoàn tất Marketplace agreement hoặc thay model production mà
chưa báo nhóm.

### 11.2. Guardrails cho AI Tutor

1.  Tuấn xác định nội dung Tutor được phép trả lời và nội dung phải từ
    chối/chuyển người hướng dẫn.
2.  Tạo Guardrail trong đúng Region sau khi chốt model/Region.
3.  Cấu hình policy phù hợp với nội dung học tập và dữ liệu người dùng.
4.  Gắn Guardrail vào lời gọi model của Tutor.
5.  Backend chỉ gửi dữ liệu tối thiểu cần thiết: lesson/context đã
    duyệt, attempt và trạng thái học tập cần thiết.
6.  Không đưa email, tên đầy đủ, password, JWT hoặc thông tin nhạy cảm
    vào prompt.
7.  Test câu hỏi hợp lệ, câu hỏi ngoài phạm vi, prompt injection cơ bản
    và trường hợp cần chuyển giảng viên.
8.  Ghi lại Guardrail ID/version và kết quả test.

### 11.3. Network cho Bedrock/Transcribe/Secrets

Vì Lambda có thể chạy trong VPC, Dũng phải xác định chính xác các AWS
API mà runtime gọi:

-   Nếu gọi Bedrock Runtime qua private network: xác minh/tạo interface
    endpoint `bedrock-runtime`.
-   Nếu đọc Secrets Manager trong VPC: xác minh/tạo endpoint tương ứng
    hoặc phương án egress được duyệt.
-   Nếu gọi Transcribe/MediaConvert từ code trong VPC: xác minh
    endpoint/egress tương ứng.
-   Kiểm tra endpoint security group cho HTTPS 443 từ Lambda SG.
-   Không tạo endpoint hoặc NAT chỉ để "thử"; mỗi endpoint/NAT có thể
    phát sinh phí.

------------------------------------------------------------------------

## 12. K6 -- CloudWatch, Alarms và AWS Budgets

**Chủ trì:** Huy.\
**Cấu hình AWS:** Dũng.\
**Cung cấp metric:** Hùng và Tuấn.

### 12.1. Log groups hiện có

Inventory ghi nhận 7 Log Groups LearnCloud ở Singapore và Sydney. Một số
log pipeline có retention 7 ngày; một số probe/hello chưa đặt retention.

Thực hiện:

1.  CloudWatch → Logs → Log groups.
2.  Xác định log group nào thuộc môi trường demo đang dùng.
3.  Đặt retention 7 hoặc 14 ngày theo nhu cầu và ngân sách.
4.  Không xóa log group còn phục vụ điều tra lỗi.
5.  Chuẩn hóa log fields: `request_id`, `lesson_id`, `execution_id`,
    `step`, `status`, `duration_ms`, `error_code`.
6.  Không log password, secret, JWT, private key, PII hoặc presigned
    URL.

### 12.2. Tạo CloudWatch Alarms

Sau khi API/pipeline có traffic test, Dũng tạo alarms tối thiểu:

  -----------------------------------------------------------------------
  Alarm                   Metric                  Mục đích
  ----------------------- ----------------------- -----------------------
  Backend Lambda Errors   Lambda `Errors`         Phát hiện lỗi Backend

  Backend Lambda          Lambda `Throttles`      Phát hiện giới hạn
  Throttles                                       concurrency

  API Gateway 5xx         API Gateway 5xx metric  Phát hiện lỗi API

  Step Functions Failed   `ExecutionsFailed`      Phát hiện pipeline thất
                                                  bại

  Step Functions TimedOut `ExecutionsTimedOut`    Phát hiện workflow
                                                  treo/quá hạn
  -----------------------------------------------------------------------

Ngưỡng cụ thể được Huy duyệt sau khi có baseline từ test. Không đặt
ngưỡng tùy tiện rồi coi alarm đã có ý nghĩa.

Nếu gửi email qua SNS:

1.  Tạo SNS topic cho LearnCloud.
2.  Tạo email subscription.
3.  Người nhận phải xác nhận subscription.
4.  Gửi test notification và xác nhận email nhận được.

### 12.3. AWS Budgets

Inventory chưa xác minh được Budgets vì AccessDenied; không kết luận
budget chưa tồn tại.

Huy kiểm tra Billing and Cost Management → Budgets. Nếu chưa có:

1.  Tạo Monthly cost budget.
2.  Tên đề xuất: `learncloud-demo-budget`.
3.  Hạn mức do Huy/nhóm phê duyệt; tài liệu cũ đề xuất ví dụ 20
    USD/tháng, không phải hạn mức bắt buộc.
4.  Tạo cảnh báo 50%, 80%, 100%.
5.  Thêm email người theo dõi.
6.  Theo dõi chi phí hằng ngày trong thời gian demo.

Budgets chỉ gửi cảnh báo, không tự động dừng tài nguyên.

------------------------------------------------------------------------

## 13. Kế hoạch kiểm thử và nghiệm thu end-to-end

Không đánh dấu LearnCloud hoàn thành chỉ vì từng dịch vụ có trạng thái
`available`. Phải kiểm tra luồng nghiệp vụ.

  ---------------------------------------------------------------------------------------
                    STT Bài kiểm tra     Kết quả mong đợi                Người
  --------------------- ---------------- ------------------------------- ----------------
                      1 Mở CloudFront    React tải qua HTTPS; S3         Hùng/Dũng
                        domain           frontend vẫn private            

                      2 Login Cognito    User demo đăng nhập, nhận JWT   Hùng
                                         hợp lệ                          

                      3 Gọi API không    Route nghiệp vụ trả 401         Huy/Dũng
                        token                                            

                      4 Gọi API có token Backend xác minh claims và trả  Huy
                                         dữ liệu đúng quyền              

                      5 Instructor       Backend cấp presigned PUT đúng  Huy/Hùng
                        tạo/upload       raw prefix                      
                        lesson                                           

                      6 Upload video     Object xuất hiện ở S3 raw;      Hùng/Tuấn
                                         không public                    

                      7 EventBridge      Một upload tạo đúng một         Tuấn/Dũng
                        trigger          workflow execution              

                      8 MediaConvert     Job hoàn tất và output đúng     Tuấn
                                         processed prefix                

                      9 Transcribe       Transcript có timestamp được    Tuấn
                                         tạo                             

                     10 Bedrock AI       Summary/sections/quiz/roadmap   Tuấn
                        Worker           đúng schema                     

                     11 Persist result   RDS/S3 có metadata và output    Huy/Tuấn
                                         bền vững                        

                     12 Instructor       Nội dung chuyển                 Huy/Hùng
                        review           `REVIEW_REQUIRED` rồi được      
                                         duyệt                           

                     13 Publish          Chỉ nội dung đã duyệt mới       Huy
                                         chuyển `PUBLISHED`              

                     14 Student access   Student chỉ xem lesson đã       Huy/Hùng
                                         publish và unlock               

                     15 Video playback   Backend cấp signed URL hợp lệ;  Huy/Hùng
                                         URL hết hạn bị từ chối          

                     16 Monitoring       Logs/alarms tra được theo       Dũng/Huy
                                         request/execution; email alert  
                                         nhận được                       

                     17 Cost             Budget và cảnh báo chi phí đã   Huy
                                         cấu hình                        
  ---------------------------------------------------------------------------------------

### Tiêu chí hoàn thành K1--K6

-   **K1:** Frontend HTTPS hoạt động, Cognito login/logout/refresh hoạt
    động, gọi API production được.
-   **K2:** Lambda FastAPI/Mangum hoạt động, API Gateway JWT authorizer
    hoạt động, authorization nghiệp vụ được kiểm tra ở Backend.
-   **K3:** RDS kết nối từ runtime được, secret không lộ, S3 private,
    upload/download đúng quyền.
-   **K4:** Một video demo đi hết workflow, có output bền vững và trạng
    thái đúng; retry không tạo job trùng.
-   **K5:** Model còn vòng đời được xác minh và invoke thành công;
    Guardrail Tutor được kiểm thử.
-   **K6:** Logs, alarms, notification và budget alert hoạt động.

------------------------------------------------------------------------

## 14. Xử lý lỗi và báo cáo tiến độ

### 14.1. Khi gặp lỗi

Không tự ý cấp `AdministratorAccess` để chữa lỗi. Gửi cho Dũng/Huy:

``` text
Người thực hiện:
IAM User / Role:
Region:
Dịch vụ:
Thao tác:
Resource ARN hoặc resource name:
Thông báo lỗi:
Mục tiêu đang làm:
Ảnh chụp màn hình (nếu có, đã che thông tin nhạy cảm):
```

Nếu là AccessDenied, người quản trị xác định quyền thiếu và bổ sung. Nếu
là ResourceNotFound, kiểm tra tên, Region, account và resource type
trước khi tạo mới.

### 14.2. Cập nhật task

Mỗi thành viên cập nhật trạng thái theo một trong các nhãn:

-   `NOT_STARTED`: Chưa bắt đầu.
-   `IN_PROGRESS`: Đang làm.
-   `BLOCKED`: Bị chặn, ghi rõ lỗi/phụ thuộc.
-   `READY_FOR_TEST`: Đã triển khai, chờ kiểm thử.
-   `DONE`: Có bằng chứng nghiệm thu.

Một task chỉ được đánh dấu DONE khi có bằng chứng: resource ARN/ID,
commit/version, test result hoặc ảnh chụp cấu hình phù hợp. Không ghi
secret trong bằng chứng.

------------------------------------------------------------------------

## 15. Backlog chi tiết theo thành viên

### 15.1. Dũng -- Admin + Cloud Deployment

**P0** - \[ \] Xác nhận các policy đã gắn cho Hùng và Tuấn; xử lý
AccessDenied phát sinh. - \[ \] Chốt registry resource, Region và
naming. - \[ \] Rà soát VPC, RDS subnet group, route table và SG. - \[
\] Xác nhận EC2 bridge còn cần hay không trước khi thay đổi inbound
5432. - \[ \] Kiểm tra secrets/network path cho Lambda. - \[ \] Kiểm tra
Lambda/API Gateway tại Singapore; chuẩn bị deploy Backend sau khi Huy
bàn giao artifact. - \[ \] Hỗ trợ Tuấn xử lý role/PassRole và pipeline
deployment.

**P1** - \[ \] Hoàn thiện private network theo phương án được Huy
duyệt. - \[ \] Tạo hoặc hoàn thiện frontend bucket và CloudFront/OAC
cùng Hùng. - \[ \] Hoàn thiện API Gateway production cùng Huy. - \[ \]
Kiểm tra targets/roles của EventBridge; không tự bật rules Disabled. -
\[ \] Cấu hình CloudWatch Alarms, SNS notification và retention. - \[ \]
Cập nhật registry ARN/ID và bằng chứng deployment.

**Đầu ra cần bàn giao:** registry tài nguyên, cấu hình hạ tầng,
execution roles, API/CloudFront endpoint, biên bản thay đổi và hướng dẫn
rollback.

### 15.2. Hùng -- Frontend

**P0** - \[ \] Xác nhận policy `AmazonS3FullAccess` đã được gắn vào
group `leanrcloud-frontend`. - \[ \] Hoàn thiện Cognito
login/logout/refresh bằng OIDC Authorization Code + PKCE. - \[ \] Bỏ
hardcode role `STUDENT`; dùng claims/backend authorization. - \[ \] Cấu
hình API base URL production. - \[ \] Hoàn thiện AuthContext, route
guard và xử lý session hết hạn. - \[ \] Kết nối
course/lesson/quiz/review/progress/Tutor với API thật.

**P1** - \[ \] Phối hợp Dũng xác định/tạo bucket frontend. - \[ \] Build
React/Vite và upload `dist` lên S3 private. - \[ \] Cấu hình CloudFront
OAC, HTTPS, SPA fallback và invalidation. - \[ \] Cập nhật Cognito
callback/logout URLs. - \[ \] Hoàn thiện upload bằng presigned PUT và
playback bằng signed URL. - \[ \] Kiểm tra giao diện trên tài khoản
Instructor và Student.

**Đầu ra cần bàn giao:** frontend URL, commit/version build, danh sách
màn hình đã tích hợp, test login/API/upload/playback.

### 15.3. Tuấn -- AI + Video Pipeline

**P0** - \[ \] Xác nhận các policy đã gắn vào group `learncloud-ai`. -
\[ \] Thay model Claude 3 Haiku LEGACY trước EOL 13/11/2026 15:00 giờ
Việt Nam. - \[ \] Chốt model ID, Region, entitlement, quota và output
schema với Huy. - \[ \] Hoàn thiện AI Worker Transcribe → transcript
timestamp → Bedrock → validated JSON. - \[ \] Hoàn thiện ASL trong
`infrastructure/step-functions/video_pipeline.asl.json`. - \[ \] Xác
định rõ Lambda AI Worker và input/output contract. - \[ \] Ghi output AI
vào S3/RDS và trả trạng thái đúng.

**P1** - \[ \] Kiểm tra MediaConvert queue/job role và Transcribe
jobs. - \[ \] Kiểm tra EventBridge pattern/targets cùng Dũng. - \[ \]
Hoàn thiện retry, timeout, deduplication và recovery. - \[ \] Tạo/kiểm
thử Guardrail cho Tutor. - \[ \] Chỉ bật retry/recovery/relay-tick sau
khi review. - \[ \] Chạy video demo end-to-end và bàn giao execution
ARN/output references.

**Đầu ra cần bàn giao:** model ID đã xác minh, AI Worker code, ASL,
execution role requirements, video test report, Guardrail ID/version.

### 15.4. Huy -- Super Admin + Backend

**P0** - \[ \] Sửa import blocker `validate_review_content`. - \[ \]
Thống nhất `APPROVED` và `PUBLISHED` giữa service/repository/schema. -
\[ \] Thay `X-Demo-User` bằng Cognito JWT claims đã xác minh. - \[ \]
Hoàn thiện `Mangum` handler và dependency. - \[ \] Hoàn thiện API
contract và authorization role/ownership/enrollment/unlock. - \[ \] Kiểm
tra DB secret integration và application DB user. - \[ \] Bàn giao
artifact Backend cho Dũng deploy.

**P1** - \[ \] Hoàn thiện API nghiệp vụ
course/lesson/review/progress/quiz/Tutor theo MVP. - \[ \] Xác nhận
migration/schema/grants với Dũng. - \[ \] Tích hợp
upload-intent/presigned PUT và signed video playback. - \[ \] Phối hợp
Tuấn thống nhất AI output schema và review status. - \[ \] Chủ trì K6:
thresholds, dashboard, runbook và nghiệm thu alerts. - \[ \] Tổng hợp
tiến độ, duyệt thay đổi rủi ro và nghiệm thu cuối.

**Đầu ra cần bàn giao:** source Backend đã test, API contract, artifact
ZIP/version, test report, quyết định trạng thái nghiệp vụ và biên bản
nghiệm thu.

------------------------------------------------------------------------

## 16. Kế hoạch thời gian đề xuất

Mốc dưới đây là kế hoạch nhóm đề xuất, không phải trạng thái đã hoàn
thành.

  -----------------------------------------------------------------------
  Thời gian                           Mục tiêu
  ----------------------------------- -----------------------------------
  **07/11/2026**                      Xác nhận quyền IAM, phân công, chốt
                                      model replacement và registry

  **08--09/11/2026**                  Tuấn hoàn tất quyết định model; Huy
                                      sửa blocker Backend; Dũng rà soát
                                      network/API; Hùng hoàn thiện
                                      Cognito integration

  **10--11/11/2026**                  Deploy Backend/API, hoàn thiện
                                      frontend hosting, hoàn thiện AI
                                      Worker/ASL

  **12/11/2026**                      Tích hợp pipeline và chạy video
                                      test end-to-end

  **Trước 13/11/2026 15:00**          Không còn dependency production vào
                                      Claude 3 Haiku LEGACY

  **13--15/11/2026**                  Hoàn thiện alarms/budget, sửa lỗi
                                      tích hợp, nghiệm thu và chuẩn bị
                                      demo
  -----------------------------------------------------------------------

Nếu một mốc bị trễ, cập nhật trạng thái `BLOCKED` và nguyên nhân; không
đánh dấu hoàn thành giả để kịp lịch.

------------------------------------------------------------------------

## 17. Chi phí, bảo mật và dọn dẹp

### Trong thời gian demo

-   Theo dõi Billing/Cost Explorer hằng ngày.
-   Chỉ dùng video ngắn và số lượng test nhỏ.
-   Kiểm soát số lần Bedrock invocation, Transcribe và MediaConvert
    jobs.
-   Không bật retry schedule liên tục khi chưa cần.
-   Theo dõi RDS, EC2 bridge, NAT/VPC endpoints và CloudFront vì có thể
    phát sinh chi phí theo thời gian.
-   Giữ S3 private; không dùng public bucket để demo.
-   Không đưa credentials vào source hoặc gửi qua nhóm chat.
-   Bật MFA cho tài khoản quản trị; không dùng chung tài khoản thành
    viên.

### Sau khi giảng viên nghiệm thu

1.  Huy xác nhận dữ liệu nào cần giữ.
2.  Dừng trigger mới bằng cách disable EventBridge rules phù hợp.
3.  Chờ execution đang chạy kết thúc hoặc xử lý theo quyết định nhóm.
4.  Sao lưu dữ liệu cần giữ.
5.  Xóa tài nguyên demo không còn cần theo thứ tự phụ thuộc.
6.  Chỉ xóa S3 bucket sau khi xác nhận dữ liệu không cần giữ và bucket
    đã được kiểm tra.
7.  Chỉ xóa RDS sau khi snapshot/backup và có xác nhận của Huy.
8.  Kiểm tra Billing để tìm tài nguyên còn chạy.
9.  Thu hồi quyền thành viên không còn tham gia.

**Không thực hiện cleanup trong lúc đang chuẩn bị demo hoặc khi chưa có
xác nhận của Huy.**

------------------------------------------------------------------------

## 18. Các quyết định nhóm cần chốt

  -----------------------------------------------------------------------
  Quyết định              Người chốt              Trạng thái
  ----------------------- ----------------------- -----------------------
  Region chính            Huy                     Đã thống nhất
  `ap-southeast-1`                                

  Huy là Root Account     Huy                     Đã thống nhất
  Owner/Super Admin                               

  Dũng là Admin/Cloud     Huy                     Đã thống nhất
  Deployment                                      

  Hùng phụ trách Frontend Huy                     Đã thống nhất

  Tuấn phụ trách AI/Video Huy                     Đã thống nhất
  Pipeline                                        

  Policy khởi đầu cho     Huy/Dũng                Đã thống nhất tên; cần
  Hùng/Tuấn                                       xác nhận đã Attach

  Giữ hay migrate RDS     Huy + Dũng              Chưa chốt
  sang dedicated private                          
  VPC                                             

  Dùng một bucket video   Huy + Dũng + Tuấn       Chưa chốt
  chia prefix hay tách                            
  raw/processed                                   

  Model Bedrock thay thế  Huy + Tuấn              P0, chưa chốt
  Haiku LEGACY                                    

  Ngưỡng AWS Budget       Huy                     Chưa chốt

  Thời điểm bật           Dũng + Tuấn             Chờ review
  retry/recovery rules                            
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 19. Kết luận

Tại ngày **07/11/2026**, LearnCloud không còn ở trạng thái "chưa có
AWS". Nhóm đã xác minh được RDS, S3 video, Lambda pipeline, Step
Functions, EventBridge, VPC, EC2 bridge và CloudWatch Logs.

Việc cần làm hiện tại là:

1.  Giữ và hoàn thiện tài nguyên đang có, tránh tạo trùng.
2.  Xử lý model Bedrock LEGACY trước hạn EOL.
3.  Hoàn thiện Backend và triển khai API production.
4.  Hoàn thiện Cognito, Frontend hosting và tích hợp API.
5.  Hoàn thiện AI Worker và nghiệm thu Video Pipeline.
6.  Hoàn thiện monitoring, budget và bảo mật.

Mọi người cập nhật task theo đúng module được giao. Khi thiếu quyền, gửi
lỗi cho Huy/Dũng để bổ sung; không tự ý mở rộng quyền hoặc thay đổi tài
nguyên ngoài phạm vi được giao.

**Mục tiêu cuối cùng:** một luồng LearnCloud chạy được từ Instructor
upload video, AI xử lý và Instructor review, đến Student truy cập lesson
đã publish/unlock, có xác thực, lưu trữ, monitoring và kiểm soát chi
phí.
