export function accountError(error) {
  const code = error?.code;
  if (error.status === 404 || error.status === 501)
    return "Dịch vụ chưa hỗ trợ thao tác này. Vui lòng thử lại sau.";
  if (error.status === 429) return "Bạn thao tác quá nhanh. Vui lòng chờ rồi thử lại.";
  if (code === "UserNotConfirmedException")
    return "Email chưa được xác minh. Hãy nhập mã xác thực đã gửi tới hộp thư.";
  if (code === "NotAuthorizedException")
    return "Email hoặc mật khẩu không đúng.";
  if (code === "CodeMismatchException" || code === "ExpiredCodeException")
    return "Mã xác thực không đúng hoặc đã hết hạn. Hãy yêu cầu mã mới.";
  if (code === "UsernameExistsException" || code === "AliasExistsException")
    return "Email này đã được đăng ký.";
  if (code === "LimitExceededException" || code === "TooManyRequestsException")
    return "Bạn thao tác quá nhanh. Vui lòng chờ rồi thử lại.";
  if (!error.status) return "Không kết nối được máy chủ. Vui lòng thử lại.";
  return error.message || "Không thực hiện được thao tác.";
}
