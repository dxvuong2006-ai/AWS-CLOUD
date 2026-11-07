import "./progress.css";

export default function ProgressBar({ value = 0, label, valueText }) {
  const v = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className="pbar">
      {(label || valueText) && (
        <div className="pbar-info">
          <span>{label}</span>
          <strong>{valueText ?? `${v}%`}</strong>
        </div>
      )}
      <div
        className="pbar-track"
        role="progressbar"
        aria-valuenow={v}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Tiến độ"}
      >
        <div className="pbar-fill" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}