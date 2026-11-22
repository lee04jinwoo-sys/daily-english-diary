import { describe, expect, it } from 'vitest';
import { popoverTop } from './popoverPosition';

const VH = 880; // viewport height

describe('popoverTop', () => {
  it('opens just below the word when the whole popover fits there', () => {
    expect(popoverTop(300, 400, VH)).toBe(312);
  });

  it('flips above the word when it does not fit below but fits above', () => {
    // a 420px popover cannot sit below a word at y=600 (612 + 420 > 864), but fits above
    expect(popoverTop(600, 420, VH)).toBe(600 - 420 - 12);
  });

  it('uses the real height: a long entry that the old fixed 270px guess let overflow now flips', () => {
    expect(popoverTop(570, 270, VH)).toBe(582);       // fits when short
    expect(popoverTop(570, 420, VH)).toBeLessThan(570); // does not fit when long
  });

  it('is pinned to the bottom margin when it fits neither below nor above', () => {
    const top = popoverTop(450, 600, VH);             // 462+600 > 864 and 450-600-12 < 16
    expect(top).toBe(VH - 600 - 16);
    expect(top + 600).toBe(VH - 16);                  // the footer stays on screen
  });

  it('keeps the top edge on screen when the popover is taller than the viewport', () => {
    expect(popoverTop(400, 2000, VH)).toBe(16);
  });

  it('never returns a position that cuts off the bottom edge when it can be avoided', () => {
    for (const y of [0, 100, 300, 500, 700, 860])
      for (const h of [200, 270, 420, 600, 800]) {
        const top = popoverTop(y, h, VH);
        expect(top).toBeGreaterThanOrEqual(16);
        expect(top + h).toBeLessThanOrEqual(VH - 16);
      }
  });
});
