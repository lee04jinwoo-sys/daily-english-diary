import { describe, expect, it } from 'vitest';
import { localDateString } from './dates';

describe('localDateString', () => {
  it('formats the local calendar day as YYYY-MM-DD', () => {
    expect(localDateString(new Date(2026, 10, 21, 9, 5))).toBe('2026-11-21');
  });

  it('pads month and day', () => {
    expect(localDateString(new Date(2026, 0, 5))).toBe('2026-01-05');
  });

  it('uses the local day, not the UTC day (just after local midnight it is still the new day)', () => {
    // 00:30 local on the 21st is the 20th in UTC for any zone east of UTC; the date must stay the 21st.
    expect(localDateString(new Date(2026, 10, 21, 0, 30))).toBe('2026-11-21');
    expect(localDateString(new Date(2026, 10, 21, 23, 59))).toBe('2026-11-21');
  });
});
