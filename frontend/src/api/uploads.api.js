import { request } from "./client";
export function videoType(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  const type = { mp4: "video/mp4", webm: "video/webm", mov: "video/quicktime" }[extension];
  if (!type || (file.type && file.type !== type)) throw new Error("Chọn video MP4, WebM hoặc MOV.");
  if (!file.size || file.size > 500 * 1024 * 1024) throw new Error("Video phải lớn hơn 0 và không quá 500 MB.");
  return type;
}
export async function uploadVideo(lessonId, file, { signal, onProgress }) {
  const contentType = videoType(file);
  const intent = await request("/lessons/" + encodeURIComponent(lessonId) + "/upload-url", {
    method: "POST", body: { filename: file.name, content_type: contentType, file_size: file.size },
  });
  if (signal.aborted) throw new DOMException("Upload cancelled", "AbortError");
  if (intent.method !== "PUT" || !/^https?:\/\//.test(intent.upload_url)) throw new Error("URL tải video không hợp lệ.");
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener("abort", abort);
    xhr.open("PUT", intent.upload_url);
    Object.entries(intent.required_headers || { "Content-Type": contentType }).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.floor(event.loaded / event.total * 100)); };
    xhr.onload = () => { cleanup(); if (xhr.status >= 200 && xhr.status < 300) resolve(intent); else reject(new Error("Tải video thất bại (HTTP " + xhr.status + "). Hãy chọn tải lại.")); };
    xhr.onerror = () => { cleanup(); reject(new Error("Mất kết nối khi tải video. Hãy thử lại.")); };
    xhr.onabort = () => { cleanup(); reject(new DOMException("Upload cancelled", "AbortError")); };
    signal.addEventListener("abort", abort, { once: true });
    xhr.send(file);
  });
}
