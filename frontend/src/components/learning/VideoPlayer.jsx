import { useEffect, useRef } from "react";
import { mergeWatchedRanges } from "../../utils/watchedRanges";

export default function VideoPlayer({
  src,
  sourceVersion = 0,
  onError,
  videoRef,
  onTimeUpdate,
  onProgress,
  startAt = 0,
}) {
  const resumePosition = useRef(null);
  useEffect(() => { if (sourceVersion > 0) videoRef.current?.load(); }, [sourceVersion, videoRef]);
  const previous = useRef(null);
  const ranges = useRef([]);
  const lastSavedAt = useRef(0);

  const beginSegment = (video) => {
    previous.current =
      !video.paused && !video.seeking && !video.ended
        ? {
            position: video.currentTime,
            wallTime: performance.now(),
            rate: video.playbackRate,
          }
        : null;
  };

  const recordSegment = (video) => {
    const now = performance.now();
    const before = previous.current;

    if (before && !video.seeking) {
      const mediaDelta = video.currentTime - before.position;
      const wallDelta = (now - before.wallTime) / 1000;

      // Kiểm tra bước tiến có hợp lý với thời gian và tốc độ phát.
      // Đây chỉ là kiểm tra phía client cho mock.
      const maxExpected = wallDelta * before.rate + 0.25;

      if (
        mediaDelta > 0 &&
        wallDelta >= 0 &&
        mediaDelta <= maxExpected
      ) {
        ranges.current = mergeWatchedRanges(
          [...ranges.current, [before.position, video.currentTime]],
          video.duration
        );
      }
    }

    beginSegment(video);
  };

  const persist = (video) => {
    if (!Number.isFinite(video.duration) || video.duration <= 0) return;

    lastSavedAt.current = performance.now();

    onProgress?.(
      video.currentTime,
      video.duration,
      ranges.current.map((range) => [...range])
    );
  };

  return (
    <div className="video-box">
      <video
        ref={videoRef}
        src={src}
        controls
        onError={onError}
        onEmptied={() => { previous.current = null; }}
        onLoadedMetadata={(event) => {
          const video = event.currentTarget;

          previous.current = null;
          lastSavedAt.current = performance.now();

          const resume = resumePosition.current ?? startAt;
          if (resume > 0 && resume < video.duration) {
            video.currentTime = resume;
          }
        }}
        onPlaying={(event) => beginSegment(event.currentTarget)}
        onTimeUpdate={(event) => {
          const video = event.currentTarget;

          recordSegment(video);
          resumePosition.current = video.currentTime;
          onTimeUpdate?.(video.currentTime);

          if (performance.now() - lastSavedAt.current >= 5000) {
            persist(video);
          }
        }}
        onSeeking={() => {
          // Không nối vị trí trước tua với vị trí sau tua.
          previous.current = null;
        }}
        onSeeked={(event) => beginSegment(event.currentTarget)}
        onRateChange={(event) => {
          // Bắt đầu đoạn mới với tốc độ mới.
          beginSegment(event.currentTarget);
        }}
        onWaiting={(event) => {
          recordSegment(event.currentTarget);
          previous.current = null;
        }}
        onPause={(event) => {
          recordSegment(event.currentTarget);
          previous.current = null;
          persist(event.currentTarget);
        }}
        onEnded={(event) => {
          recordSegment(event.currentTarget);
          previous.current = null;
          persist(event.currentTarget);
        }}
      />
    </div>
  );
}