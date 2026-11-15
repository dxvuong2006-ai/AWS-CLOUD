export function mergeWatchedRanges(ranges, duration) {
  if (!Number.isFinite(duration) || duration <= 0) return [];

  const sorted = ranges
    .filter(
      (range) =>
        Array.isArray(range) &&
        range.length === 2 &&
        Number.isFinite(range[0]) &&
        Number.isFinite(range[1])
    )
    .map(([start, end]) => [
      Math.max(0, Math.min(start, duration)),
      Math.max(0, Math.min(end, duration)),
    ])
    .filter(([start, end]) => end > start)
    .sort((a, b) => a[0] - b[0]);

  const merged = [];

  for (const [start, end] of sorted) {
    const last = merged[merged.length - 1];

    if (last && start <= last[1]) {
      last[1] = Math.max(last[1], end);
    } else {
      merged.push([start, end]);
    }
  }

  return merged;
}

export function getWatchedSeconds(ranges) {
  return ranges.reduce((total, [start, end]) => total + end - start, 0);
}