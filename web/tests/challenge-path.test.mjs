import assert from "node:assert/strict";
import test from "node:test";
import {
  pageTarget,
  railBounds,
  revealTarget,
} from "../src/challenge-path-layout.ts";
import { milestoneLayout, progressFraction } from "../src/stage-progress.ts";

test("navigation edges tolerate fractional browser measurements and resize", () => {
  assert.deepEqual(
    railBounds({ scrollLeft: 0, clientWidth: 1000, scrollWidth: 1000 }),
    { overflowing: false, previous: false, next: false },
  );
  assert.deepEqual(
    railBounds({ scrollLeft: 0, clientWidth: 335, scrollWidth: 3248 }),
    { overflowing: true, previous: false, next: true },
  );
  assert.deepEqual(
    railBounds({ scrollLeft: 2912.5, clientWidth: 335, scrollWidth: 3248 }),
    { overflowing: true, previous: true, next: false },
  );
  assert.equal(
    railBounds({ scrollLeft: 0, clientWidth: 3250, scrollWidth: 3250 })
      .overflowing,
    false,
  );
});

test("mobile paging aligns whole cards, including after touch scrolling and at the end", () => {
  const offsets = Array.from({ length: 14 }, (_, index) => 6 + index * 232);
  const rail = { scrollLeft: 0, clientWidth: 335, scrollWidth: 3252 };
  assert.equal(pageTarget(rail, -1, offsets), 0);
  assert.equal(pageTarget(rail, 1, offsets), 232);
  assert.equal(pageTarget({ ...rail, scrollLeft: 232 }, 1, offsets), 464);
  assert.equal(pageTarget({ ...rail, scrollLeft: 232 }, -1, offsets), 0);
  assert.equal(pageTarget({ ...rail, scrollLeft: 57 }, 1, offsets), 232);
  assert.equal(pageTarget({ ...rail, scrollLeft: 300 }, 1, offsets), 464);
  assert.equal(pageTarget({ ...rail, scrollLeft: 300 }, -1, offsets), 0);
  assert.equal(pageTarget({ ...rail, scrollLeft: 2900 }, 1, offsets), 2917);
  assert.equal(pageTarget({ ...rail, scrollLeft: 2917 }, 1, offsets), 2917);
  assert.equal(pageTarget({ ...rail, scrollLeft: 2917 }, -1, offsets), 2784);
  assert.equal(pageTarget(rail, 1, []), 0);
});

test("desktop paging advances several whole cards from measured offsets", () => {
  const offsets = Array.from({ length: 14 }, (_, index) => 6 + index * 232);
  const rail = { scrollLeft: 0, clientWidth: 1360, scrollWidth: 3252 };
  assert.equal(pageTarget(rail, 1, offsets), 1160);
  assert.equal(pageTarget({ ...rail, scrollLeft: 1160 }, -1, offsets), 0);
  assert.equal(pageTarget({ ...rail, scrollLeft: 1160 }, 1, offsets), 1892);
  assert.equal(pageTarget({ ...rail, scrollLeft: 100 }, 1, offsets), 1392);
  assert.equal(pageTarget({ ...rail, scrollLeft: 1892 }, -1, offsets), 696);
  // Actual layout measurements, rather than a hard-coded card size or gap.
  assert.equal(
    pageTarget({ ...rail, clientWidth: 500 }, 1, [10, 310, 620, 970]),
    300,
  );
});

test("selected-card reveal moves only enough to fit and remains bounded", () => {
  const rail = { scrollLeft: 0, clientWidth: 335, scrollWidth: 3248 };
  assert.equal(revealTarget(rail, 6, 224), 0);
  assert.equal(revealTarget(rail, 3024, 224), 2913);
  assert.equal(revealTarget({ ...rail, scrollLeft: 250 }, 6, 224), 0);
  assert.equal(revealTarget({ ...rail, scrollLeft: 250 }, 300, 224), 250);
});

test("a five-challenge desktop path needs neither paging nor reveal movement", () => {
  const rail = { scrollLeft: 0, clientWidth: 1360, scrollWidth: 1360 };
  assert.equal(railBounds(rail).overflowing, false);
  assert.equal(revealTarget(rail, 1090, 264), 0);
});

test("projector gives five and fourteen challenges readable individual marks", () => {
  for (const total of [5, 14]) {
    const layout = milestoneLayout(total, 480);
    assert.equal(layout.individual, true);
    assert.deepEqual(
      layout.labels,
      Array.from({ length: total }, (_, i) => i + 1),
    );
  }
});

test("long or narrow projector paths use sparse milestones and the exact final total", () => {
  for (const [total, width] of [
    [30, 480],
    [14, 240],
    [103, 400],
  ]) {
    const layout = milestoneLayout(total, width);
    assert.equal(layout.individual, false);
    assert.equal(layout.labels[0], 0);
    assert.equal(layout.labels.at(-1), total);
    assert.ok(layout.labels.length <= Math.floor(width / 32) + 1);
    for (let index = 1; index < layout.labels.length; ++index)
      assert.ok(
        ((layout.labels[index] - layout.labels[index - 1]) / total) * width >=
          32,
      );
  }
  assert.deepEqual(milestoneLayout(0, 480).labels, []);
});

test("aggregate fill retains exact partial progress for long paths and empty rooms", () => {
  assert.equal(progressFraction(7, 30), 7 / 30);
  assert.equal(progressFraction(14, 14), 1);
  assert.equal(progressFraction(0, 0), 0);
  assert.equal(progressFraction(20, 14), 1);
});
