# Hướng dẫn nhập Route cho API Gateway và Cognito

- Ngày: 2026-11-08
- Mục tiêu: Hướng dẫn điền màn hình tạo route trong API Gateway khi triển khai Cognito cho LearnCloud.
- Tài liệu đã kiểm tra: `docs/aws-deployment.md` (mục 9), `docs/api-contract.md`, `agent/output/LEARNCLOUD_AWS_INVENTORY_FINAL.md`, `agent/output/COGNITO_BACKEND_IMPLEMENTATION_REPORT_2026-11-07.md`.
- Source code đã kiểm tra: các router FastAPI hiện có và báo cáo triển khai Cognito backend.

## Kết quả

Màn hình “Route and method” là để định tuyến request của API Gateway tới integration, không phải nơi nhập thông tin Cognito. Theo hướng dẫn triển khai LearnCloud, tạo hai route:

| Method | Path | Mục đích |
|---|---|---|
| `ANY` | `/` | Request ở root |
| `ANY` | `/{proxy+}` | Chuyển tiếp các đường dẫn API FastAPI |

Gán cả hai route vào Lambda integration của backend. Sau đó tạo JWT authorizer riêng trong **Authorization → Manage authorizers → Create**: issuer URL dùng Cognito User Pool issuer; Audience dùng App client ID. Gán authorizer vào các route nghiệp vụ. Có thể để `/health` public nếu cần health check.

Nếu đang ở màn hình tạo một route, nhập `ANY` vào Method và `/{proxy+}` vào Path để bắt đầu; sau đó thêm `ANY /` riêng. Không nhập `Cognito`, `/auth/login`, hay `/pets` vào ô path này chỉ vì đang cấu hình Cognito.

Inventory cuối trong repo có ghi nhận API `learncloud-api` với `GET /hello` và chưa có authorizer tại thời điểm inventory. Vì vậy trước khi thêm, kiểm tra API/stage đang thao tác để tránh tạo API trùng hoặc nhầm với API cũ. Tình trạng AWS hiện tại chưa được truy vấn lại trong nhiệm vụ này.

## Kiểm thử / bằng chứng

Không thực hiện thao tác AWS hoặc kiểm thử request trực tiếp. Hướng dẫn dựa trên cấu hình được ghi trong `docs/aws-deployment.md`; chưa xác nhận route hay authorizer đã tồn tại/hoạt động trên AWS.

## Vấn đề còn lại và bước tiếp theo

- Xác nhận đúng HTTP API và Lambda integration của LearnCloud trước khi lưu route.
- Tạo JWT authorizer theo User Pool issuer và App client ID, rồi gán vào route nghiệp vụ.
- Sau khi deploy, kiểm tra request thiếu token trả 401 và token hợp lệ đi tới backend.
