export function accountError(error) {
  if (error.status === 404 || error.status === 501)
    return "Dịch vụ chưa hỗ trợ thao tác này. Vui lòng thử lại sau.";
  if (error.status === 429) return "Bạn thao tác quá nhanh. Vui lòng chờ rồi thử lại.";
  if (!error.status) return "Không kết nối được máy chủ. Vui lòng thử lại.";
  return error.message || "Không thực hiện được thao tác.";
}
