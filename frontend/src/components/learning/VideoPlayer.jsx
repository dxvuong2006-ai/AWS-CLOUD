export default function VideoPlayer({ src, videoRef, onTimeUpdate, startAt = 0, onPause, onEnded }) {
  return (
    <div className="video-box">
      <video
        ref={videoRef}
        src={src}
        controls
        onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (startAt > 0 && startAt < v.duration - 2) v.currentTime = startAt;
          }}
        onPause={onPause}
        onEnded={onEnded}
        onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      />
    </div>
  );
}