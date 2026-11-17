# Đối soát danh tính Cognito/RDS

Tài liệu này là runbook vận hành để phân loại và xử lý lệch danh tính giữa Cognito và RDS; đây không phải migration hay bằng chứng production. Nội dung được đối chiếu với source ngày 17/11/2026, nhưng inventory Cognito/RDS hiện hành chưa được kiểm tra và mọi thao tác ghi cần change request riêng.

## Kết luận rà soát

- Frontend đăng nhập trực tiếp bằng Cognito `USER_PASSWORD_AUTH`; backend không
  có endpoint `/auth/login` cho Cognito. Sau đăng nhập, frontend dùng access token
  gọi `GET /auth/me`.
- Cognito access token thường có `sub` và `username`, nhưng không có `email`.
  Phiên bản backend cũ chỉ tạo `public.users` khi claims có `email`, vì vậy một
  Cognito user đã xác nhận vẫn có thể không bao giờ có profile RDS.
- `POST /auth/verify-email` xác nhận Cognito trước rồi mới tạo profile RDS. Nếu
  bước đọc/ghi DB lỗi sau khi Cognito đã xác nhận, lần retry cũ dừng ở lỗi “đã
  confirmed” và không repair phần RDS.
- Cơ chế cũ cập nhật `name`/`email` trên row đã có trong một số đường sync. Điều
  này không cần thiết cho authentication và có thể ghi đè dữ liệu RDS.
- `users.role` là nguồn phân quyền duy nhất. Cognito groups không được dùng để tự
  cấp `INSTRUCTOR` hoặc `ADMIN`.
- `POST /admin/users` hiện là workflow hai hệ thống: tạo Cognito trước, rồi mới
  insert RDS. Hai bước không thể nằm trong cùng database transaction. Nếu bước
  RDS thất bại sau khi Cognito thành công, account cần reconciliation thủ công;
  first-login chỉ được phép tạo `STUDENT`, tuyệt đối không suy role từ Cognito
  group. Muốn tự động hoá đầy đủ về sau cần provisioning request/outbox có ID
  riêng và trạng thái review, không được coi email là khóa idempotency.

## Chính sách cấp profile sau khi sửa

1. Tìm profile theo exact `cognito_sub`.
2. Nếu đã có, trả row hiện tại và không cập nhật `name`, `email`, `role`,
   `password_hash` hay `cognito_sub`.
3. Nếu chưa có và access token thiếu email, dùng signed `username` claim để gọi
   `AdminGetUser`, sau đó bắt buộc `sub` trả về phải trùng token.
4. Nếu email đã thuộc bất kỳ row RDS nào nhưng exact `cognito_sub` chưa khớp,
   fail closed; không liên kết theo email.
5. Chỉ khi cả `sub` và email đều chưa tồn tại mới tạo một row với role
   `STUDENT`.
6. Nếu hai request đầu tiên chạy đồng thời, unique constraint chọn một winner;
   request còn lại chỉ chấp nhận row winner khi cả `sub` và email cùng khớp.
7. Retry verify của một Cognito user đã `CONFIRMED` được phép tiếp tục repair RDS
   sau khi đọc lại trạng thái Cognito; các trạng thái khác vẫn bị từ chối.
8. Identity mới chỉ được provision khi `AdminGetUser` trả `Enabled=true`,
   `UserStatus=CONFIRMED`, `email_verified=true` và exact `sub` trùng access token.
   `UNCONFIRMED`, `FORCE_CHANGE_PASSWORD`, user disabled hoặc email chưa verified
   đều không tạo row RDS.

## IAM cho Lambda backend

Template least-privilege nằm tại
`infrastructure/iam/lambda-auth-cognito-permissions.json`. Nếu toàn bộ FastAPI
routes chạy chung một Lambda execution role, role hiện cần đúng tám actions sau trên
ARN của một User Pool cụ thể:

- `cognito-idp:AdminGetUser` cho first-login/verify provisioning;
- `cognito-idp:AdminCreateUser`;
- `cognito-idp:AdminSetUserPassword`;
- `cognito-idp:AdminAddUserToGroup`;
- `cognito-idp:AdminRemoveUserFromGroup`;
- `cognito-idp:AdminUpdateUserAttributes`.
- `cognito-idp:AdminDisableUser` and `cognito-idp:AdminEnableUser` for the admin account status endpoint.

Nếu tách admin routes sang Lambda khác, Lambda auth thông thường chỉ cần
`AdminGetUser`; bảy quyền quản trị còn lại thuộc Lambda admin. `SignUp`, `ConfirmSignUp`,
`ResendConfirmationCode`, `ForgotPassword`, `ConfirmForgotPassword` là public
Cognito operations và `ChangePassword` được authorize bằng access token, nên
không thêm chúng vào execution-role policy. JWKS HTTPS read cũng không phải IAM
action. Thay placeholders `AWS_REGION`, `ACCOUNT_ID`, `COGNITO_USER_POOL_ID` khi
review/deploy; không dùng resource `*`.

## Kế hoạch đối soát production

Trước khi ghi dữ liệu, operator cần xuất hai snapshot chỉ đọc: Cognito gồm
`Username`, `sub`, `email`, `email_verified`, `UserStatus`, `Enabled`; RDS gồm
`id`, `cognito_sub`, `email`, `name`, `role`, `created_at`. Chuẩn hoá email về
lowercase chỉ để so sánh, không cập nhật dữ liệu ở bước audit.

Phân loại từng Cognito user:

- `EXACT_SUB`: có row cùng `cognito_sub`; không làm gì, kể cả khi profile drift.
- `SAFE_MISSING`: không có row cùng `sub` và không có row cùng email. Sau khi code
  mới được triển khai, lần gọi `/auth/me` hợp lệ sẽ tự tạo profile `STUDENT`.
  Nếu cần backfill trước login, phải dùng một change request riêng, transaction
  riêng cho từng identity và giữ role `STUDENT`.
- `EMAIL_CONFLICT`: không có exact `sub`, nhưng email đã có trong RDS. Không tự
  động sửa; chuyển sang review thủ công.
- `SUB_CONFLICT`: cùng `sub` nhưng dữ liệu chỉ ra hai chủ thể khác nhau. Khoá xử
  lý và điều tra; không copy role hoặc dữ liệu giữa các row.

Không đưa email, user ID, Cognito subject hoặc danh sách account thực vào tài liệu công khai. Operator phải giữ bảng phân loại `EXACT_SUB`/`SAFE_MISSING`/`EMAIL_CONFLICT`/`SUB_CONFLICT` trong nơi lưu trữ riêng có kiểm soát truy cập. Với mỗi conflict, xác minh lịch sử hai hệ thống, quyền sở hữu account và các bản ghi nghiệp vụ tham chiếu; chỉ cập nhật exact `cognito_sub` khi có change request, backup và precondition được duyệt. Nếu chưa đủ bằng chứng, giữ nguyên xung đột và từ chối liên kết là kết quả an toàn.

## Kiểm tra sau đối soát

Chỉ dùng truy vấn `SELECT` để xác nhận:

- không có `cognito_sub` trùng;
- không có email trùng khi so sánh `lower(email)`;
- mỗi identity đã xử lý có exact `sub` match;
- role trước/sau không đổi, ngoại trừ row `STUDENT` mới được tạo;
- ID 10 không đổi nếu chưa có change request được duyệt.

Sau đó smoke test bằng token của từng user: `/auth/me` phải trả cùng một `id` qua
nhiều lần gọi, và không tạo thêm row ở lần thứ hai.
