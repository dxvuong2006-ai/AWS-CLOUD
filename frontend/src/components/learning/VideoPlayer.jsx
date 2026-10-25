export default function VideoPlayer({ src, videoRef, onTimeUpdate }) {
  return (
    <div className="video-box">
      <video
        ref={videoRef}
        src={src}
        controls
        onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
      />
    </div>
  );
}