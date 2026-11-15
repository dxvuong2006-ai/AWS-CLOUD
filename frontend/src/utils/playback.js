export function acceptedPlaybackRange(before, position, now, seeking) {
  if (!before || seeking || !Number.isFinite(position) || !Number.isFinite(now)) return null;
  const delta = position - before.position;
  const elapsed = (now - before.wallTime) / 1000;
  if (!Number.isFinite(before.rate) || before.rate <= 0 || delta <= 0 || elapsed < 0 || delta > elapsed * before.rate + 0.25) return null;
  return [before.position, position];
}
// Serialize writes so a late request cannot restore an older resume position.
// Each payload contains cumulative intervals, allowing the next save to recover after a failure.
export function createSerialWriter(write) {
  let tail = Promise.resolve();
  return payload => {
    const result = tail.then(() => write(payload));
    tail = result.catch(() => {});
    return result;
  };
}
