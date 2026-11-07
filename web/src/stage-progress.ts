export function progressFraction(solved: number, total: number) {
  return total > 0 ? Math.max(0, Math.min(1, solved / total)) : 0;
}

// A challenge gets a distinct mark only when it has enough screen space.
// Long paths use an exact continuous fill and a sparse numeric milestone axis.
export function milestoneLayout(total: number, width: number) {
  if (total <= 0) return { individual: false, labels: [] as number[] };
  if (width >= total * 24)
    return {
      individual: true,
      labels: Array.from({ length: total }, (_, index) => index + 1),
    };
  const intervals = Math.max(1, Math.floor(width / 64));
  const needed = total / intervals;
  const magnitude = 10 ** Math.floor(Math.log10(needed));
  const stride =
    [1, 2, 5, 10].find((size) => size * magnitude >= needed)! * magnitude;
  const labels = [0];
  for (let mark = stride; mark < total; mark += stride) {
    // Leave enough room for the exact final total instead of colliding labels.
    if (((total - mark) / total) * width >= 32) labels.push(mark);
  }
  labels.push(total);
  return { individual: false, labels };
}
