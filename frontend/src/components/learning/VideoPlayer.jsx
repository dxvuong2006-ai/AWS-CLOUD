export default function VideoPlayer({ src, videoRef, onTimeUpdate, startAt = 0, onPause, onEnded }) {
  if (typeof src !== "string" || !src.trim()) {
    return <div className="card"><p>Chưa có video</p></div>;
  }

  return (
    <div className="video-box">
      <video
        ref={videoRef}
        src={src.trim()}
        controls
        onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (Number.isFinite(startAt) && startAt > 0 && startAt < v.duration - 2) {
              v.currentTime = startAt;
            }
          }}
        onPause={onPause}
        onEnded={onEnded}
        onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      />
    </div>
  );
}
