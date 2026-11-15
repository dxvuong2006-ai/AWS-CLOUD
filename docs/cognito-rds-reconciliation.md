# Cognito/RDS identity reconciliation

Tài liệu này là kế hoạch vận hành, không phải migration. Thay đổi code trong đợt
audit này không kết nối RDS/Cognito production và không tự chạy `INSERT`,
`UPDATE`, `DELETE`.

## Kết luận audit

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

## Chính sách provisioning sau sửa

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
routes chạy chung một Lambda execution role, role cần đúng sáu actions sau trên
ARN của một User Pool cụ thể:

- `cognito-idp:AdminGetUser` cho first-login/verify provisioning;
- `cognito-idp:AdminCreateUser`;
- `cognito-idp:AdminSetUserPassword`;
- `cognito-idp:AdminAddUserToGroup`;
- `cognito-idp:AdminRemoveUserFromGroup`;
- `cognito-idp:AdminUpdateUserAttributes`.
- `cognito-idp:AdminDisableUser` and `cognito-idp:AdminEnableUser` for the admin account status endpoint.

Nếu tách admin routes sang Lambda khác, Lambda auth thông thường chỉ cần
`AdminGetUser`; năm quyền ghi thuộc Lambda admin. `SignUp`, `ConfirmSignUp`,
`ResendConfirmationCode`, `ForgotPassword`, `ConfirmForgotPassword` là public
Cognito operations và `ChangePassword` được authorize bằng access token, nên
không thêm chúng vào execution-role policy. JWKS HTTPS read cũng không phải IAM
action. Thay placeholders `AWS_REGION`, `ACCOUNT_ID`, `COGNITO_USER_POOL_ID` khi
review/deploy; không dùng resource `*`.

## Kế hoạch reconciliation production

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

Theo hiện trạng đã cung cấp, ba email sau là ứng viên `SAFE_MISSING` **chỉ khi
snapshot tại thời điểm xử lý vẫn xác nhận không có row cùng email hoặc sub**:

- `nemarsanto1@gmail.com`
- `ok@gmail.com`
- `dxvuong2007@gmail.com`

Không suy ra role cũ cho ba tài khoản này. Cơ chế first-login chỉ tạo `STUDENT`.
Nếu nghiệp vụ yêu cầu role khác, admin phải thực hiện quy trình cấp quyền riêng.

`o@gmail.com` đã gọi `/auth/me` thành công nên chỉ cần kiểm tra `EXACT_SUB`; không
cập nhật row nếu đã khớp.

## Xử lý riêng RDS user ID 10

`vuongthuy1998@gmail.com` phải được phân loại `EMAIL_CONFLICT`: row ID 10 và
Cognito hiện tại có `cognito_sub` khác nhau. Backend mới sẽ từ chối liên kết và
giữ nguyên ID 10, role, tên, email, password hash và subject cũ.

Operator cần xác minh ngoài hệ thống:

1. Subject cũ còn tồn tại trong đúng User Pool hay không.
2. Lịch sử tạo/cập nhật row ID 10 và lịch sử Cognito của cả hai subject.
3. Chủ tài khoản đã chứng minh quyền sở hữu email và account nào là account cần
   giữ lại.
4. Có dữ liệu nghiệp vụ tham chiếu ID 10 (course, enrollment, progress, attempt)
   hay không.

Chỉ khi review kết luận Cognito subject hiện tại chính là chủ thể hợp lệ của row
ID 10, một change request được duyệt mới được phép thay exact `cognito_sub` trong
transaction có backup và kiểm tra precondition. Không đổi role, không đổi ID,
không ghi đè profile. Nếu chưa đủ bằng chứng, giữ nguyên xung đột và từ chối đăng
nhập là kết quả an toàn.

## Kiểm tra sau reconciliation

Chỉ dùng truy vấn `SELECT` để xác nhận:

- không có `cognito_sub` trùng;
- không có email trùng khi so sánh `lower(email)`;
- mỗi identity đã xử lý có exact `sub` match;
- role trước/sau không đổi, ngoại trừ row `STUDENT` mới được tạo;
- ID 10 không đổi nếu chưa có change request được duyệt.

Sau đó smoke test bằng token của từng user: `/auth/me` phải trả cùng một `id` qua
nhiều lần gọi, và không tạo thêm row ở lần thứ hai.
