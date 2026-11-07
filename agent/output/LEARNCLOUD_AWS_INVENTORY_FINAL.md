# LearnCloud — Kiểm kê AWS thực tế

Ngày kiểm kê: **07/11/2026**, mẫu metadata khoảng **00:04–00:09 giờ Việt Nam (UTC+7)**. Profile duy nhất: **`learncloud-audit-ro`**.

**Kết luận:** LearnCloud đã triển khai một phần hạ tầng dữ liệu và video pipeline tại Singapore: một bucket video, RDS PostgreSQL, VPC/SG/endpoints, ba Lambda pipeline/relay/recovery, Step Functions, bốn rule EventBridge và các log groups. Workflow có lịch sử chạy, nhưng chưa xác minh end-to-end. K1 chưa đủ bằng chứng; backend đích `learncloud-api-prod` không tìm thấy đúng tên tại Singapore; API đang thấy ở Sydney chỉ có `GET /hello`, không authorizer. Model mặc định trong source đang LEGACY tại Singapore và đã báo hết vòng đời tại Sydney/us-east-1. Nhiều cấu hình sâu vẫn AccessDenied.

Không sửa source, CLI profile, IAM hay tài nguyên AWS; không deploy; không chạy workload hoặc kiểm thử chức năng mới.

## 1. Danh tính và phạm vi

Lệnh đầu tiên dùng đúng profile, sau đó chạy lại cùng lệnh ngoài sandbox để truy cập cấu hình sẵn có:

```powershell
aws sts get-caller-identity --profile learncloud-audit-ro --output json --no-cli-pager
```

Kết quả xác minh:

```json
{
  "Account": "697589240877",
  "Arn": "arn:aws:sts::697589240877:assumed-role/LearnCloudAuditReadOnlyRole/learncloud-inventory"
}
```

Đúng account và audit role **`LearnCloudAuditReadOnlyRole`**. Lỗi “profile could not be found” chỉ xảy ra trong sandbox; ngoài sandbox profile hoạt động. Không chuyển sang `learncloud`, default, root hoặc identity khác. Trước mỗi đợt lệnh, script tiếp tục kiểm tra Account/ARN của chính profile này và dừng nếu không khớp.

Phạm vi:

- **ap-southeast-1:** K1–K6 và mạng LearnCloud chính.
- **ap-southeast-2:** đối chiếu API mẫu và tài nguyên cùng vùng theo repo.
- **us-east-1:** Bedrock fallback trong source; endpoint cho IAM/CloudFront/Budgets và kiểm tra discovery theo tag.
- S3 ListBuckets kiểm kê general-purpose buckets của account; không đọc object. CloudFront OAC/key groups/public-key metadata theo phạm vi global.
- DescribeRegions trả 34 Region: 17 `opt-in-not-required`, 17 `not-opted-in`. **Không kiểm kê toàn bộ dịch vụ tại 17 Region đang dùng được**; các Region ngoài phạm vi trên vẫn chưa xác minh.

Nguồn đối chiếu: [PDF, mục 2.3 trang 29–39](../agent/PROGRESS_2_AWS_FINAL.pdf), [báo cáo tiến độ](LEARNCLOUD_PROGRESS_REVIEW.md), [audit cũ](../agent/aws-audit-2026-11-06/LEARNCLOUD_AWS_AUDIT.md), source và `infrastructure/`. Phân công dùng bản mới: **Dũng — Admin + Cloud Deployment; Hùng — Frontend + Web Hosting; Tuấn — AI + Video Pipeline; Huy — Backend Code + Giám sát**.

### Quy tắc đọc dữ liệu đã áp dụng

Chỉ các API metadata thuộc mục 7 của báo cáo tiến độ; mọi AWS CLI invocation đều có `--profile learncloud-audit-ro`. Không gọi GetSecretValue/SSM GetParameter, Lambda ListFunctions/GetFunction/GetFunctionConfiguration/ListVersions, Cognito client detail, S3 object APIs, SQL, log events/Insights, workflow DescribeExecution/history, MediaConvert jobs, Transcribe job detail, Bedrock invoke/apply hoặc API nghiệp vụ.

Không gọi CloudFront ListDistributions/GetDistributionConfig và API Gateway integration/stage detail vì response có thể chứa custom-header secrets/stage variables. Không gọi EventBridge ListTargetsByRule vì có thể trả Input/InputTransformer chứa payload. Chỉ lọc CLI bằng `--query` không bảo đảm tránh truy xuất secrets; do đó các API này được **bỏ qua**, không chỉ lọc output.

## 2. Bằng chứng và ý nghĩa trạng thái

Bộ bằng chứng gồm **185 bản ghi** trong bốn JSON, ngoài các lần thử STS ban đầu: **116 thành công, 65 AccessDenied, 4 ResourceNotFoundException**. Bốn bản ghi STS kiểm tra lại danh tính nằm trong bộ này. Không có API mutation/runtime invocation.

| File | Bản ghi | Kết quả |
|---|---:|---|
| [01-discovery.json](aws-inventory-2026-11-07/01-discovery.json) | 69 | 53 OK, 16 AccessDenied |
| [02-details.json](aws-inventory-2026-11-07/02-details.json) | 89 | 45 OK, 44 AccessDenied |
| [03-final-checks.json](aws-inventory-2026-11-07/03-final-checks.json) | 23 | 16 OK, 5 AccessDenied, 2 Function not found |
| [04-model-metadata.json](aws-inventory-2026-11-07/04-model-metadata.json) | 4 | 2 OK, 2 model-version end-of-life |

Mỗi bản ghi có lệnh/Region/thời gian UTC/kết quả; chỉ giữ metadata được chọn. Script kiểm kê và manifests ở [thư mục bằng chứng](aws-inventory-2026-11-07/). Không chạy lại các script audit cũ có API trả environment/jobs.

- **Tồn tại:** API đọc metadata thành công cho đối tượng/ID cụ thể.
- **Cấu hình phù hợp từng phần:** chỉ xác nhận thuộc tính đã đọc, không suy ra toàn bộ integration đúng.
- **Chức năng đã kiểm thử:** phiên này **không có kiểm thử mới**. Execution history summaries/metric names/log bytes chỉ chứng minh hoạt động được ghi nhận trước đó, không thay nghiệm thu học liệu.
- **Không tìm thấy có phạm vi:** response rỗng hoặc ResourceNotFound cho đúng loại/tên/Region đã kiểm tra; không mở rộng thành “không có trên toàn AWS”.
- **AccessDenied:** thiếu quyền quan sát, không chứng minh tài nguyên vắng mặt. ARN xuất hiện trong lỗi quyền không phải bằng chứng existence.

## 3. Trạng thái K1–K6

| Khối / đích PDF | Tài nguyên thực tế và cấu hình đã đọc | Chưa xác minh / sai lệch | Đánh giá |
|---|---|---|---|
| **K1:** S3 frontend, CloudFront/OAC, Cognito | S3 chỉ trả một bucket account-owned là bucket video. CloudFront OAC, key groups, public-key lists không có item. Cognito user pools trả rỗng tại Singapore và Sydney | Chưa có bucket frontend riêng trong danh sách general-purpose buckets; không đọc object nên chưa biết bucket video có chứa web hay không. Distribution chưa kiểm kê vì rủi ro custom-header secret; tag discovery AccessDenied. Cognito ở Region khác chưa kiểm tra | **Chưa có bằng chứng hoàn thiện K1**; không kết luận CloudFront distribution không tồn tại |
| **K2:** API Gateway → Lambda FastAPI/Mangum trong VPC | Singapore: REST APIs và HTTP APIs đều rỗng. Sydney: HTTP API `learncloud-api`, chỉ `GET /hello`, AuthorizationType `NONE`, authorizers rỗng. Hai Lambda probe Singapore và Lambda hello Sydney tồn tại | `learncloud-api-prod` trả Function not found tại Singapore qua hai API an toàn. Không liệt kê toàn bộ Lambda/config nên có thể còn function tên khác. Chưa xác minh integration target/handler/runtime/VPC binding hoặc backend nghiệp vụ | **Mới xác nhận API mẫu/probes**, chưa chứng minh backend đích triển khai |
| **K3:** RDS PostgreSQL, S3 raw/processed, private network | RDS `learncloud-db` postgres 16.9, available, encrypted, PubliclyAccessible=false; bucket video ở Singapore; SG5432 theo source SG; ba endpoints available | DB subnets thuộc default VPC, route chính có Internet Gateway; chưa đúng topology private subnet trong PDF. S3 public access/encryption/CORS/Lifecycle/notification/prefixes đều chưa đọc được. Secret provider metadata AccessDenied; schema/migrations không kiểm tra SQL | **Hạ tầng tồn tại, cấu hình chỉ xác minh một phần** |
| **K4:** EventBridge, SFN, MediaConvert, Transcribe, Pipeline Lambda | Workflow STANDARD; ba Lambda video tồn tại; bốn rules default bus; upload ENABLED, retry/recovery/relay-tick DISABLED. Có bốn executions: 2 SUCCEEDED, 2 FAILED | Rule patterns, targets, workflow definition/config/role binding chưa xác minh. MediaConvert queues và Transcribe job metadata AccessDenied. Không đọc payload/log/output. Không biết execution thành công kết thúc nhánh nào | **Đã triển khai phần điều phối/video**, chưa chứng minh Transcribe/AI hoặc E2E |
| **K5:** Bedrock; Guardrails cho Tutor | Đọc được model/catalogue availability và system-defined inference profiles. Haiku trong source có ARN tại Singapore nhưng lifecycle LEGACY. Guardrails trả rỗng tại ba Region | Model-version detail ở Sydney/us-east-1 báo end-of-life; availability trả các trường khác nhau, không đủ xác nhận invoke. Không có bằng chứng Tutor/Guardrail runtime; system-defined profiles không phải tài nguyên ứng dụng tự triển khai | **Metadata Bedrock đã đọc; chưa xác nhận ứng dụng AI hoạt động; cần xử lý model** |
| **K6:** CloudWatch Logs/Metrics/Alarms, Budgets | Bảy log groups LearnCloud ở hai Region; bốn pipeline log groups retention 7 ngày; có tên metric Lambda/SFN | Alarms và Budgets AccessDenied. Ba probe/hello groups không đặt retention. Không đọc nội dung log hoặc metric values; notification delivery chưa kiểm thử. SNS topics rỗng tại hai Region | **Logging/metric metadata đã có; cảnh báo và chi phí chưa xác minh** |

PDF yêu cầu Secrets Manager **hoặc** Parameter Store, endpoint theo API thực gọi/NAT thay thế, S3 Lifecycle và Guardrails riêng cho Tutor. Không mặc định thêm SNS/SQS/NAT vào danh sách bắt buộc; chúng chỉ là phụ trợ theo lựa chọn triển khai.

## 4. Registry tài nguyên được xác minh

ARN RDS, workflow, rules, roles, policies, log groups và model được trả qua metadata. S3/API/EC2 ARN dưới đây được **chuẩn hóa từ tên/ID và Region đã xác minh**, không phải mọi API đều trả trường ARN. ARN Lambda được dùng làm đích ListTags thành công; không lấy configuration/environment.

### 4.1. Singapore — ap-southeast-1

| Tài nguyên | ARN / ID được xác minh | Chi tiết |
|---|---|---|
| S3 video | `arn:aws:s3:::learncloud-videos-mentorcloud` | Region xác nhận bằng ListBuckets có pagination; không suy từ tên hoặc endpoint gọi. Bucket tạo 03/11/2026. Vai trò raw/processed theo source; chưa xác nhận nội dung/prefix |
| RDS | `arn:aws:rds:ap-southeast-1:697589240877:db:learncloud-db` | Postgres16.9, db.t3.micro, available, encrypted, single-AZ; backup retention1 ngày; deletion protection=false; IAM DB auth=false; chưa có enabled log exports trong response |
| Lambda pipeline | `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-pipeline` | ListAliases/ListTags thành công; không có alias hoặc tag |
| Lambda relay | `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-relay` | Tồn tại; không có alias/tag |
| Lambda recovery | `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-video-recovery` | Tồn tại; không có alias/tag |
| Lambda RDS probe | `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-rds-probe` | Tồn tại; không thay backend nghiệp vụ |
| Lambda network probe | `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-network-probe` | Tồn tại; không thay bằng chứng kết nối hiện tại |
| Step Functions | `arn:aws:states:ap-southeast-1:697589240877:stateMachine:learncloud-video-pipeline` | STANDARD; creation metadata 03/11; DescribeStateMachine METADATA_ONLY vẫn AccessDenied |
| EventBridge upload | `arn:aws:events:ap-southeast-1:697589240877:rule/learncloud-video-upload` | ENABLED, default bus; target/pattern chưa xác minh |
| EventBridge retry | `arn:aws:events:ap-southeast-1:697589240877:rule/learncloud-video-retry` | DISABLED |
| EventBridge recovery | `arn:aws:events:ap-southeast-1:697589240877:rule/learncloud-video-recovery` | DISABLED |
| EventBridge relay tick | `arn:aws:events:ap-southeast-1:697589240877:rule/learncloud-video-relay-tick` | DISABLED; schedule `rate(1 minute)` |
| VPC | `vpc-0255e992edb53b226` | Default VPC, available; ARN chuẩn hóa `arn:aws:ec2:ap-southeast-1:697589240877:vpc/vpc-0255e992edb53b226` |
| EC2 bridge | `i-0c9692401b32c5922` | running; instance-profile `arn:aws:iam::697589240877:instance-profile/learncloud-ssm-ec2-role`; không mở phiên SSM |

**Lambda đích chưa tồn tại đúng tên tại Singapore:** `arn:aws:lambda:ap-southeast-1:697589240877:function:learncloud-api-prod`. ListAliases và ListTags đều trả ResourceNotFoundException “Function not found”. Đây không phải AccessDenied; không mở rộng kết luận sang function tên khác hoặc Region khác.

### 4.2. Network và RDS topology

| Thành phần | ID / cấu hình đã đọc |
|---|---|
| RDS subnet group | `default-vpc-0255e992edb53b226` |
| Subnets | `subnet-0fe6b4574b0251d46` (1c), `subnet-0b153276529deac83` (1b), `subnet-0687e946cc0eac915` (1a); cả ba MapPublicIpOnLaunch=true |
| Main route table | `rtb-001d612a1f3cee4eb`: local172.31/16; `0.0.0.0/0 → igw-0d2ca76eddf430ec9`; S3 prefix list → gateway endpoint. Không có route table riêng/explicit subnet associations khác trong inventory |
| S3 Gateway endpoint | `vpce-00183670494f23bde`, available; gắn route table trên |
| MediaConvert Interface endpoint | `vpce-06c492ac0968c437b`, available, private DNS=true, chỉ subnet1b, SG `learncloud-vpce-sg` |
| EventBridge Interface endpoint | `vpce-0e8715c1d14f0231c`, available, private DNS=true, chỉ subnet1b, cùng endpoint SG |
| NAT | ListNatGateways trả rỗng trong Singapore |
| RDS SG | `sg-047b6fe18a2919fa9` — TCP5432 từ Lambda SG `sg-09f12414802976b54` và EC2 bridge SG `sg-0a85f63e968d8f96d`; không có CIDR Internet ingress5432 |
| Lambda SG | `sg-09f12414802976b54` — không ingress; egress5432 tới RDS SG; egress443 tới endpoint SG và S3 prefix list |
| Endpoint SG | `sg-0cb219747d286dcc9` — ingress443 từ Lambda SG; không có egress rules |
| Bridge SG | `sg-0a85f63e968d8f96d` — không ingress, egress all IPv4 |

**Cần xử lý thiết kế:** PubliclyAccessible=false là cấu hình RDS đã xác nhận; nó không làm các subnet có route Internet Gateway trở thành private subnets. PDF yêu cầu private subnet và SG RDS chỉ từ Lambda; hiện còn quyền5432 từ bridge quản trị cần chủ dự án xác nhận ngoại lệ. Không có endpoint Bedrock/Transcribe/Secrets Manager/SSM hoặc NAT trong inventory VPC này. Với runtime gắn vào Lambda SG đã đọc, đường egress hiện chỉ tới RDS, S3 và hai interface endpoints; cần chốt mạng cho AI/secret provider trước tích hợp. Chưa đọc Lambda VPC attachment, nên không khẳng định mọi function đang dùng SG này.

### 4.3. Sydney — ap-southeast-2

| Tài nguyên | ARN / ID | Metadata |
|---|---|---|
| HTTP API | ID `fq5w2z5s66`; ARN chuẩn hóa `arn:aws:apigateway:ap-southeast-2::/apis/fq5w2z5s66` | `learncloud-api`; route duy nhất `GET /hello`, auth NONE; target là integration ID, chưa đọc integration detail; authorizers rỗng; CORS chưa cấu hình trong API metadata |
| Lambda hello | `arn:aws:lambda:ap-southeast-2:697589240877:function:learncloud-hello` | ListAliases/ListTags thành công; không alias/tag; chưa xác minh API integration hiện trỏ tới function này |
| Log group | `arn:aws:logs:ap-southeast-2:697589240877:log-group:/aws/lambda/learncloud-hello:*` | Không đặt retention |
| Default VPC | `vpc-0e4db8c6f7a6ce8cc` | Ba default subnets; không có VPC endpoint/NAT trong inventory; chưa gắn với backend đích |

Tại Sydney, RDS instances/clusters, default-bus rules và state machines đều trả rỗng. Đây là kết quả có phạm vi Region, không phải kết luận toàn account.

## 5. Lịch sử pipeline và K6

ListExecutions trả **bốn execution summaries**, không đọc name/input/output/history payload:

| Bắt đầu — giờ Việt Nam | Trạng thái | Dừng |
|---|---|---|
| 04/11/2026 00:30:37 | SUCCEEDED | 00:32:16 |
| 04/11/2026 00:09:30 | SUCCEEDED | 00:10:39 |
| 03/11/2026 22:48:31 | FAILED | 22:48:36 |
| 03/11/2026 22:33:26 | FAILED | 22:33:31 |

Đây là bằng chứng workflow đã có hoạt động, **chưa chứng minh video/AI end-to-end đúng**. Source ASL có cả DuplicateIgnored và VideoReadyAIPending kết thúc Succeed. Không biết executions trên đi nhánh nào hoặc có output thật vì không đọc payload/log/database/S3.

Singapore có sáu log groups. ARN dùng prefix `arn:aws:logs:ap-southeast-1:697589240877:log-group:` cộng tên nhóm và suffix `:*`, đều đã nhận từ DescribeLogGroups:

| Log group | Retention | StoredBytes |
|---|---:|---:|
| `/aws/lambda/learncloud-video-pipeline` | 7 ngày | 5239 |
| `/aws/lambda/learncloud-video-relay` | 7 ngày | 3512 |
| `/aws/lambda/learncloud-video-recovery` | 7 ngày | 656 |
| `/aws/vendedlogs/states/learncloud-video-pipeline` | 7 ngày | 1896 |
| `/aws/lambda/learncloud-network-probe` | Chưa đặt | 1495 |
| `/aws/lambda/learncloud-rds-probe` | Chưa đặt | 695 |

Sydney có thêm hello group nêu ở mục4.3, StoredBytes4163. Không đọc byte nội dung nào. Không có retentionInDays nghĩa là chưa đặt thời hạn hết hạn theo log-group metadata.

ListMetrics xác nhận các series Lambda như Invocations/Errors/Throttles/Duration/ConcurrentExecutions cho pipeline; SFN có ExecutionsStarted/Succeeded/Failed/TimedOut/Aborted/ExecutionTime và các metric khác. Chưa đọc datapoint, chưa đánh giá tỷ lệ lỗi/độ trễ. DescribeAlarms và Budgets bị AccessDenied; không kết luận chưa tạo alarm/budget. SNS ListTopics trả rỗng ở Singapore/Sydney, không loại trừ kênh khác hoặc Region khác.

## 6. Bedrock, model và Guardrails

Model source mặc định: `anthropic.claude-3-haiku-20240307-v1:0`.

| Region | Model metadata | Model availability metadata |
|---|---|---|
| ap-southeast-1 | ARN **`arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0`**; lifecycle **LEGACY**, ON_DEMAND; metadata ghi endOfLifeTime **13/11/2026 15:00 giờ Việt Nam** | AUTHORIZED; entitlement AVAILABLE; Region AVAILABLE; agreement **NOT_AVAILABLE** |
| ap-southeast-2 | GetFoundationModel trả ResourceNotFoundException: phiên bản đã hết vòng đời | Availability vẫn trả AUTHORIZED/AVAILABLE/AVAILABLE và agreement NOT_AVAILABLE |
| us-east-1 | GetFoundationModel trả cùng lỗi phiên bản hết vòng đời | Availability trả các trường tương tự |

**P0 cho Tuấn:** chốt model còn vòng đời phù hợp, Region, quyền và contract output trước nghiệm thu; fallback us-east-1 trong source hiện không thể mặc định coi an toàn cho phiên bản này. Không tự đổi model hoặc hoàn tất marketplace agreement. Metadata availability và catalogue không đồng nhất ở hai Region; không suy ra invoke thành công/thất bại chỉ từ một trường. Không có inference nào được chạy trong audit.

ListGuardrails trả rỗng tại cả ba Region. ListInferenceProfiles trả 39/50/99 item tương ứng, **tất cả SYSTEM_DEFINED**; không thấy APPLICATION profile trong kết quả. Các system profiles/model catalogue là dịch vụ AWS cung cấp, không tính thành 188 tài nguyên LearnCloud đã triển khai. Chưa có Guardrail cho Tutor được xác minh trong ba Region đã kiểm tra; Region khác ngoài phạm vi.

## 7. IAM users, groups, policies và execution roles

### 7.1. Users và groups

ListUsers xác nhận **4 IAM users**; ListGroups xác nhận **4 groups**. Membership sau lấy từ ListGroupsForUser cho cả bốn users, dù GetGroup riêng bị từ chối:

| User / ARN | Groups | Policy trực tiếp |
|---|---|---|
| `arn:aws:iam::697589240877:user/Dung` | `learncloud-admin`, `learncloud-backend` | Không attached/inline user policies |
| `arn:aws:iam::697589240877:user/Hung` | **`leanrcloud-frontend`** — tên thực tế có lỗi chính tả | Không attached/inline user policies |
| `arn:aws:iam::697589240877:user/Tuan` | `learncloud-ai` | Không attached/inline user policies |
| `arn:aws:iam::697589240877:user/learncloud-backend-dev` | Không group | Attached `LearnCloudS3VideoPolicy`; inline names `LearnCloud-Assume-Audit-Role`, `LearnCloud-RDS-SSM-Tunnel`; nội dung inline AccessDenied |

Group ARNs là `arn:aws:iam::697589240877:group/` cộng đúng tên nhóm đã đọc:

| Group | Managed policies đã gắn | Inline policies |
|---|---|---|
| `learncloud-admin` | AdministratorAccess, AmazonAPIGatewayAdministrator, AmazonCognitoPowerUser, SecretsManagerReadWrite, AmazonRDSReadOnlyAccess, CloudWatchFullAccessV2, AWSLambda_FullAccess | Không |
| `leanrcloud-frontend` | CloudFrontFullAccess | Không |
| `learncloud-ai` | AmazonTranscribeFullAccess, CloudWatchReadOnlyAccess, AmazonBedrockFullAccess | Không |
| `learncloud-backend` | Không | Không |

Chưa có IAM user tên `Huy` trong ListUsers; **không mặc định** `learncloud-backend-dev` thuộc Huy. Dũng cần xác nhận mapping người→identity. Nhóm backend hiện không có identity policy gắn trực tiếp vào group; không kết luận người trong group không có quyền vì còn quyền từ nguồn khác. Các FullAccess/AdministratorAccess attachments cần đối chiếu least privilege theo trách nhiệm mới; không sửa trong audit. Chưa tính effective permissions dưới SCP/boundaries/resource policies.

### 7.2. Execution/audit roles

ListRoles xác nhận **15 roles**, gồm 10 role liên quan LearnCloud bên dưới và 5 service-linked roles cho API Gateway, RDS, Resource Explorer, Support, Trusted Advisor. Trust policy được đọc từ **ListRoles**; GetRole riêng bị AccessDenied nên boundaries/chi tiết bổ sung chưa xác minh. Có role không đồng nghĩa function/workflow đang sử dụng role đó.

| Role / ARN | Trusted principal | Policy attachments/inline names đã thấy |
|---|---|---|
| `arn:aws:iam::697589240877:role/LearnCloudAuditReadOnlyRole` | IAM user `learncloud-backend-dev` | AWS managed **ViewOnlyAccess**; không inline |
| `arn:aws:iam::697589240877:role/learncloud-rds-probe-role` | Lambda service | AWSLambdaBasicExecutionRole, AWSLambdaVPCAccessExecutionRole |
| `arn:aws:iam::697589240877:role/service-role/learncloud-hello-role-1wk0srb2` | Lambda service | Customer-managed basic-execution policy nêu dưới |
| `arn:aws:iam::697589240877:role/learncloud-ssm-ec2-role` | EC2 service | AmazonSSMManagedInstanceCore |
| `arn:aws:iam::697589240877:role/LearnCloudVideoPipelineLambdaRole` | Lambda service | AWSLambdaVPCAccessExecutionRole, LearnCloudVideoPipelineBootstrapPolicy; inline LearnCloudLambdaMediaConvertPolicy, LearnCloudLambdaS3Policy |
| `arn:aws:iam::697589240877:role/LearnCloudVideoRelayLambdaRole` | Lambda service | AWSLambdaVPCAccessExecutionRole, LearnCloudVideoRelayPolicy |
| `arn:aws:iam::697589240877:role/LearnCloudVideoRecoveryLambdaRole` | Lambda service | AWSLambdaVPCAccessExecutionRole, LearnCloudVideoRecoveryPolicy |
| `arn:aws:iam::697589240877:role/LearnCloudVideoMediaConvertRole` | MediaConvert service | Inline LearnCloudMediaConvertS3Policy; không managed attachment |
| `arn:aws:iam::697589240877:role/LearnCloudVideoStateMachineRole` | Step Functions service | LearnCloudVideoStepFunctionsPolicy |
| `arn:aws:iam::697589240877:role/LearnCloudVideoEventBridgeRole` | EventBridge service | LearnCloudVideoEventBridgePolicy; trust có SourceAccount697589240877 và SourceArn giới hạn rule `learncloud-video-*` ở Singapore |

ViewOnlyAccess được gắn vào audit role là sự thật attachment; không chứng minh mọi quyền đọc cần thiết đã có. Không đọc được nội dung managed/inline policy, nên chưa kết luận quyền S3/MediaConvert/PassRole/model đủ hoặc đúng scope.

### 7.3. Customer-managed policies

ListPolicies scope Local trả bảy policies, default version đều v1, mỗi policy AttachmentCount1:

- `arn:aws:iam::697589240877:policy/LearnCloudS3VideoPolicy`
- `arn:aws:iam::697589240877:policy/LearnCloudVideoRecoveryPolicy`
- `arn:aws:iam::697589240877:policy/LearnCloudVideoPipelineBootstrapPolicy`
- `arn:aws:iam::697589240877:policy/LearnCloudVideoStepFunctionsPolicy`
- `arn:aws:iam::697589240877:policy/LearnCloudVideoRelayPolicy`
- `arn:aws:iam::697589240877:policy/LearnCloudVideoEventBridgePolicy`
- `arn:aws:iam::697589240877:policy/service-role/AWSLambdaBasicExecutionRole-3363b2c1-3986-41ba-adc5-2aaaaeae6374`

GetPolicyVersion của cả bảy đều AccessDenied. GetUserPolicy/GetRolePolicy của các inline names đã liệt kê cũng AccessDenied. Templates trong repo không được coi là policy document đang áp dụng.

## 8. Những phần chưa xác minh

| Nguyên nhân | Phần bị giới hạn |
|---|---|
| **AccessDenied — S3** | Location getter, public access block, policy/status, CORS, encryption, ownership controls, versioning, website, notification, Lifecycle. Region đã lấy được bằng ListBuckets pagination; những thuộc tính còn lại vẫn chưa rõ |
| **AccessDenied — K4** | events:ListEventBuses/DescribeRule; states:DescribeStateMachine dù dùng METADATA_ONLY; mediaconvert:ListQueues; transcribe:ListTranscriptionJobs. Không suy ra thiếu bus/config/queue/job |
| **AccessDenied — Lambda/IAM** | lambda:GetFunctionConcurrency; iam:GetGroup/GetRole/GetPolicyVersion/GetUserPolicy/GetRolePolicy. Tồn tại Lambda vẫn xác minh được bằng ListAliases/ListTags; roles/trust qua ListRoles |
| **AccessDenied — K6/secrets/discovery** | cloudwatch:DescribeAlarms; budgets:ViewBudget; secretsmanager:ListSecrets; ssm:DescribeParameters; tag:GetResources |
| **Chủ động bỏ qua để tránh secrets/payload** | CloudFront distributions/config, Lambda configuration/versions/code, Cognito client detail, API integration/stages, EventBridge targets, workflow inputs/outputs/history, log bodies, MediaConvert full jobs và Transcribe transcript URL |
| **Ngoài phạm vi** | Các dịch vụ/Region khác; toàn bộ Lambda tên khác; nội dung S3/DB; migrations và DB grants; runtime env flags, current deployed code/hash/handler/role binding; network/function connectivity và end-to-end tests |

Không đổi profile, không tự gắn thêm quyền và không thử quyền ghi để kiểm chứng audit role. Các khoảng trống trên cần bằng chứng cấu hình đã loại secrets từ chủ tài nguyên hoặc đợt đọc metadata phù hợp được chủ account cho phép; **không có yêu cầu cấp quyền quản trị** trong báo cáo này.

## 9. Đối chiếu source và backlog theo phân công mới

Rà soát source hiện tại tiếp tục thấy `X-Demo-User`, API Tutor/progress/analytics và AuthContext còn khung; hai service import `validate_review_content` nhưng review_service không định nghĩa; review_repo đặt PUBLISHED còn publish_course yêu cầu APPROVED. ASL source còn placeholder AI worker. Đây là blocker **của source đang kiểm tra**, không chứng minh bản đang chạy trên Lambda giống source này. Không import/chạy test ứng dụng hoặc đọc `.env`.

| Module | Ưu tiên và công việc còn lại | Bằng chứng/điều kiện hoàn tất |
|---|---|---|
| **Dũng — Admin + Cloud Deployment** | **P0:** chốt registry/naming và Region; xác minh CloudFront an toàn và kiến trúc một bucket chia prefix hay tách frontend/raw/processed. Xác nhận mapping IAM cho Huy. Rà soát group FullAccess/AdministratorAccess, role policies và khoảng trống audit; không tự sửa trong phiên này | ARN/owner/config có bằng chứng rõ; tên group frontend giữ đúng tên thực tế khi đối chiếu; không tạo tài nguyên trùng |
| Dũng | **P0:** thiết kế private subnets/routes theo PDF; xác nhận ngoại lệ RDS SG từ bridge; chốt egress cho Bedrock/Transcribe/secret provider, runtime VPC binding và endpoint policies | PubliclyAccessible=false cùng topology/SG đúng mục tiêu; kiểm thử kết nối ở đợt riêng, không suy từ endpoint available |
| Dũng | **P1:** xác minh rồi triển khai phần backend/K1 còn thiếu tại Region đích sau khi Huy/Hùng hoàn thiện; kiểm tra target/pattern/role của upload; quyết định bật retry/recovery/relay-tick sau review an toàn | Không tự bật ba rule đang DISABLED; graph/targets/ARN/permission scope được duyệt và nghiệm thu |
| **Hùng — Frontend + Web Hosting** | **P0:** hoàn thiện Cognito OIDC/PKCE/login/refresh/logout, bỏ hardcode STUDENT; nối API production và UI/client upload/quiz/Tutor/review | Không dùng hello hoặc mock thay backend nghiệp vụ; backend vẫn quyết định enrollment/unlock |
| Hùng | **P1:** phối hợp Dũng chọn bucket frontend/distribution/OAC và quyền hosting; build/deploy web sau khi hạ tầng được xác minh; chốt CloudFront signed playback hay S3 presigned khác PDF | Web hosting/SPA/CORS/callback/HTTPS đúng môi trường; không đưa AWS credentials lên trình duyệt |
| **Tuấn — AI + Video Pipeline** | **P0:** thay kế hoạch phụ thuộc Haiku LEGACY/EOL bằng model/Region còn hỗ trợ theo quyết định nhóm; chốt IAM/model entitlement/quota và Guardrail Tutor. Singapore metadata ghi EOL13/11/2026 15:00 | Model/configuration được xác minh; không coi AVAILABLE hay system profiles là inference đã chạy; không tự thay trong audit |
| Tuấn | **P0:** hoàn thiện AI worker Transcribe→transcript timestamp→Bedrock→schema→durable output/proof; phối hợp Huy sửa validation/state contract và contract run/owner/attempt | Không dùng manual review/fallback để chứng minh workflow tự động hoàn tất; xác nhận nhánh ReviewRequired có output thật |
| Tuấn | **P1:** kiểm tra MC/Transcribe jobs an toàn, retries/dedup/recovery/timeout và ba nhánh Succeed; cung cấp telemetry cho Huy; hoàn thiện Tutor remediation/context/Guardrails | Nghiệm thu riêng bằng video demo; không tự publish, không job trùng; rule disabled chỉ bật sau review triển khai |
| **Huy — Backend Code + Giám sát** | **P0:** sửa import blocker, thống nhất APPROVED/PUBLISHED, thay X-Demo-User bằng Cognito JWT/sub/role validation; hoàn thiện Mangum/handler và API còn khung | Source load/package được và contract nhất quán trong đợt test riêng; giao artifact cho Dũng, không dùng probe thay backend |
| Huy | **P1:** tích hợp DB secret-provider runtime, xác nhận schema/migrations/grants với chủ DB; giữ upload-intent/outbox và authorization cho playback | Không suy file SQL đã chạy; không log password/token/presigned URL; deployed version/config có bằng chứng đã loại secrets |
| Huy | **P1 — chủ trì K6:** đối chiếu alarm/Budgets, định nghĩa thresholds/dimensions/dashboard/runbook; xử lý retention ba group probe/hello theo nhu cầu; phối hợp Dũng provision, Tuấn cung cấp run/job telemetry, Hùng hiển thị monitoring | Phân biệt metric/log group tồn tại với alarm config và notification delivery hoạt động; chỉ đọc metadata an toàn cho audit |

### Cập nhật so với báo cáo trước

Các ghi chú README “AWS NOT DEPLOYED” hoặc audit cũ AccessDenied không còn đủ để mô tả toàn bộ tiến độ: lần này đã chứng minh RDS, bucket, Lambda video, workflow, rules và logs **thực sự tồn tại**. Tuy vậy không sửa nhãn thành AWS VERIFIED cho toàn pipeline: chưa xác minh cấu hình đầy đủ hoặc chức năng E2E. Không dùng tỷ lệ phần trăm hoàn thành khi các hạng mục chưa có tiêu chí/bằng chứng tương đương.

## 10. Tài liệu kỹ thuật đối chiếu

- S3 ListBuckets có pagination trả BucketRegion, giúp xác minh Region mà không cần đọc object: [AWS ListBuckets](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListBuckets.html).
- Lambda ListFunctions có thể chứa Environment; audit dùng ListAliases/ListTags theo allowlist thay vì đọc configuration: [AWS ListFunctions response](https://docs.aws.amazon.com/lambda/latest/api/API_ListFunctions.html).
- DescribeStateMachine hỗ trợ METADATA_ONLY; phiên này vẫn bị từ chối nên không có bằng chứng ASL đang deploy: [AWS DescribeStateMachine](https://docs.aws.amazon.com/step-functions/latest/apireference/API_DescribeStateMachine.html).
- Budgets DescribeBudget/DescribeBudgets được ánh xạ tới IAM ViewBudget; AccessDenied không có nghĩa chưa có budget: [AWS Budgets authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_budgets.html).

**Kết thúc kiểm kê:** đúng audit role, đã ghi ARN/Region/tồn tại và cấu hình đọc được, ghi riêng mọi lỗi quyền/phần bỏ qua, không đọc dữ liệu nhạy cảm và không thay đổi AWS/source.
