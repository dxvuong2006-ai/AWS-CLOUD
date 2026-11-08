import { useRef, useState } from "react";

function videoErrorMessage(error) {
  if (error?.code === "VIDEO_NOT_AVAILABLE") return "Chưa có video";
  if (error?.status === 404) return "Không tìm thấy video của bài học.";
  if (error?.status === 401) return "Vui lòng đăng nhập lại để xem video.";
  if (error?.status === 403) return "Bạn không có quyền xem video này.";
  if (error?.status === 409) return "Video chưa sẵn sàng để phát MP4.";
  return "Không tải được video. Vui lòng thử lại.";
}

export default function VideoPlayer({
  src, videoRef, onTimeUpdate, startAt = 0, onPause, onEnded,
  loading = false, error = null, onRefresh,
}) {
  const restore = useRef(null);
  const refreshing = useRef(false);
  const recoveryAttempts = useRef(0);
  const recoveredAt = useRef(0);
  const [mediaError, setMediaError] = useState(false);
  const hasSource = typeof src === "string" && !!src.trim();

  const renew = async (force = false) => {
    if (!onRefresh || refreshing.current) return;
    const video = videoRef.current;
    const snapshot = video && {
      time: video.currentTime,
      resume: !video.paused && !video.ended,
      rate: video.playbackRate,
    };
    refreshing.current = true;
    restore.current = snapshot;
    try {
      const result = await onRefresh(force);
      if (!result) {
        restore.current = null;
      } else if (video && video.getAttribute("src") === result.video_url) {
        // S3 can return the same signature for requests within the same second.
        video.load();
      }
      if (result) setMediaError(false);
    } finally {
      refreshing.current = false;
    }
  };

  const retry = () => {
    recoveryAttempts.current = 0;
    setMediaError(false);
    if (onRefresh) renew(true);
    else videoRef.current?.load();
  };

  return (
    <div className={hasSource ? undefined : "card"}>
      {loading && <p role="status">Đang tải video...</p>}
      {(error || mediaError) && (
        <div role="alert">
          <p>{error ? videoErrorMessage(error) : "Không phát được video. Vui lòng thử lại."}</p>
          <button type="button" className="btn-secondary" disabled={loading} onClick={retry}>
            Thử lại video
          </button>
        </div>
      )}
      {!hasSource && !loading && !error && <p>Chưa có video</p>}
      {hasSource && (
        <div className="video-box">
          <video
            ref={videoRef}
            src={src.trim()}
            controls
            playsInline
            preload="metadata"
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              const snapshot = restore.current;
              restore.current = null;
              const position = snapshot?.time ?? startAt;
              if (Number.isFinite(position) && position > 0 && position < video.duration) {
                video.currentTime = position;
              }
              if (snapshot) video.playbackRate = snapshot.rate;
              if (snapshot?.resume) video.play().catch(() => {});
            }}
            onPlay={() => renew()}
            onSeeking={() => renew()}
            onError={() => {
              setMediaError(true);
              if (onRefresh && recoveryAttempts.current < 1) {
                recoveryAttempts.current += 1;
                recoveredAt.current = videoRef.current?.currentTime ?? 0;
                renew(true);
              }
            }}
            onPause={onPause}
            onEnded={onEnded}
            onTimeUpdate={(event) => {
              const time = event.currentTarget.currentTime;
              if (time > recoveredAt.current + 5) recoveryAttempts.current = 0;
              onTimeUpdate?.(time);
            }}
          />
        </div>
      )}
    </div>
  );
}
