import { request } from "./client";
export function videoType(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  const type = { mp4: "video/mp4", webm: "video/webm", mov: "video/quicktime" }[extension];
  if (!type || (file.type && file.type !== type)) throw new Error("Chọn video MP4, WebM hoặc MOV.");
  if (!file.size || file.size > 500 * 1024 * 1024) throw new Error("Video phải lớn hơn 0 và không quá 500 MB.");
  return type;
}
export const confirmVideoUpload = (lessonId, uploadId) => request(
  "/lessons/" + encodeURIComponent(lessonId) + "/confirm-upload",
  { method: "POST", body: { upload_id: uploadId } },
);
export async function uploadVideo(lessonId, file, { signal, onProgress }) {
  const contentType = videoType(file);
  const intent = await request("/lessons/" + encodeURIComponent(lessonId) + "/upload-url", {
    method: "POST", body: { filename: file.name, content_type: contentType, file_size: file.size },
  });
  if (signal.aborted) throw new DOMException("Upload cancelled", "AbortError");
  if (intent.method !== "PUT" || !/^https?:\/\//.test(intent.upload_url) || !/^[a-f0-9]{32}$/.test(intent.upload_id)
      || intent.required_headers?.["If-None-Match"] !== "*")
    throw new Error("Backend chưa trả lượt upload hợp lệ; chưa gửi video. Hãy cập nhật Backend.");
  let transferError;
  try { await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener("abort", abort);
    xhr.open("PUT", intent.upload_url);
    Object.entries(intent.required_headers || { "Content-Type": contentType }).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.floor(event.loaded / event.total * 100)); };
    xhr.onload = () => { cleanup(); if ((xhr.status >= 200 && xhr.status < 300) || [409, 412].includes(xhr.status)) resolve(); else reject(new Error("Tải video thất bại (HTTP " + xhr.status + "). Hãy thử tiếp tục cùng lượt upload.")); };
    xhr.onerror = () => { cleanup(); reject(new Error("Mất kết nối khi tải video. Hãy thử lại.")); };
    xhr.onabort = () => { cleanup(); reject(new DOMException("Upload cancelled", "AbortError")); };
    signal.addEventListener("abort", abort, { once: true });
    xhr.send(file);
  }); } catch (error) { transferError = error; }
  // PUT/network errors may arrive after S3 committed the object. Confirm the
  // server-issued immutable key; never allocate another key as a fallback.
  try { return await confirmVideoUpload(lessonId, intent.upload_id); }
  catch (error) {
    if (transferError && error.code === "UPLOAD_OBJECT_NOT_FOUND") throw transferError;
    throw error;
  }
}
