function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function TranscriptPanel({ segments, currentTime, onSeek }) {
  const activeIndex = segments.reduce(
    (acc, seg, i) => (seg.start <= currentTime ? i : acc),
    -1
  );

  return (
    <div className="card">
      <h3 className="card-title">Transcript</h3>
      <div className="transcript-list">
        {segments.map((seg, i) => (
          <button
            key={seg.start}
            className={`transcript-row${i === activeIndex ? " active" : ""}`}
            onClick={() => onSeek(seg.start)}
          >
            <span className="time-chip">{formatTime(seg.start)}</span>
            <span>{seg.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}