export interface RailGeometry {
  scrollLeft: number;
  clientWidth: number;
  scrollWidth: number;
}

export function railBounds(rail: RailGeometry) {
  const end = Math.max(0, rail.scrollWidth - rail.clientWidth);
  return {
    overflowing: end > 2,
    previous: rail.scrollLeft > 2,
    next: rail.scrollLeft < end - 2,
  };
}

function clampToRail(rail: RailGeometry, left: number) {
  return Math.max(0, Math.min(left, rail.scrollWidth - rail.clientWidth));
}

export function pageTarget(
  rail: RailGeometry,
  direction: -1 | 1,
  itemOffsets: readonly number[],
) {
  // Offset from the first card keeps the rail's own focus gutter intact.
  const positions = itemOffsets.map((left) => left - itemOffsets[0]);
  const candidates = positions.filter((left) =>
    direction === 1 ? left > rail.scrollLeft + 2 : left < rail.scrollLeft - 2,
  );
  const inPage = candidates.filter(
    (left) => Math.abs(left - rail.scrollLeft) <= rail.clientWidth + 2,
  );
  const target =
    direction === 1
      ? (inPage.at(-1) ?? candidates[0])
      : (inPage[0] ?? candidates.at(-1));
  return clampToRail(rail, target ?? rail.scrollLeft);
}

// Move only as far as necessary; an already visible card must not snap back.
export function revealTarget(
  rail: RailGeometry,
  itemLeft: number,
  itemWidth: number,
  inset = 6,
) {
  if (itemLeft < rail.scrollLeft + inset)
    return clampToRail(rail, itemLeft - inset);
  if (itemLeft + itemWidth > rail.scrollLeft + rail.clientWidth - inset)
    return clampToRail(rail, itemLeft + itemWidth - rail.clientWidth + inset);
  return clampToRail(rail, rail.scrollLeft);
}
