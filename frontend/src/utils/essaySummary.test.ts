import { describe, expect, it } from 'vitest';
import { EssayListItem } from '../types/essay';
import { bandDelta, weakestCriteria, wordsPerMinute } from './essaySummary';

// the list is newest first, like the sidebar
const essay = (id: string, band: number | null, extra: Partial<EssayListItem> = {}): EssayListItem => ({
  id, date: '2026-11-01', prompt: 'p', essay_type: 'free', category: 'free', word_count: 300, revision_of: null,
  is_reviewed: band != null, is_completed: false, overall_band: band, writing_seconds: 0, preview: '', updated_at: '',
  bands: null, correction_count: 0, grammar_count: 0, ...extra,
});

describe('wordsPerMinute', () => {
  it('is words over minutes, one decimal', () => {
    expect(wordsPerMinute(364, 42 * 60)).toBe(8.7);
    expect(wordsPerMinute(400, 60)).toBe(400);
  });
  it('is unknown when there is no usable writing time', () => {
    expect(wordsPerMinute(300, 0)).toBeNull();
    expect(wordsPerMinute(300, 59)).toBeNull();
  });
  it('is unknown without words', () => {
    expect(wordsPerMinute(0, 3000)).toBeNull();
  });
});

describe('bandDelta', () => {
  it('compares with the previous reviewed essay (the next one down in a newest-first list)', () => {
    const list = [essay('c', 6.5), essay('b', null), essay('a', 6.0)];
    expect(bandDelta(list[0], list)).toBe(0.5); // skips the unreviewed one
  });
  it('is negative when the band dropped and zero when it did not change', () => {
    const list = [essay('c', 6.0), essay('b', 6.5), essay('a', 6.5)];
    expect(bandDelta(list[0], list)).toBe(-0.5);
    expect(bandDelta(list[1], list)).toBe(0);
  });
  it('has nothing to compare for the first reviewed essay or an unreviewed one', () => {
    const list = [essay('b', null), essay('a', 6.0)];
    expect(bandDelta(list[0], list)).toBeNull();
    expect(bandDelta(list[1], list)).toBeNull();
  });
  it('compares a rewrite with the essay it rewrites, not with the previous essay', () => {
    const list = [essay('rew', 7.0, { revision_of: 'orig' }), essay('other', 5.0), essay('orig', 6.0)];
    expect(bandDelta(list[0], list)).toBe(1);
  });
  it('falls back to the previous essay when the original has no band', () => {
    const list = [essay('rew', 7.0, { revision_of: 'orig' }), essay('prev', 6.5), essay('orig', null)];
    expect(bandDelta(list[0], list)).toBe(0.5);
  });
  it('does not accumulate float noise', () => {
    const list = [essay('b', 6.7), essay('a', 6.4)];
    expect(bandDelta(list[0], list)).toBe(0.3);
  });
});

describe('weakestCriteria', () => {
  const bands = (tr: number, cc: number, lr: number, gr: number) =>
    ({ task_response: tr, coherence: cc, lexical: lr, grammar: gr });
  it('is the lowest criterion', () => {
    expect(weakestCriteria(bands(6.5, 6.0, 6.0, 5.5))).toEqual(['grammar']);
  });
  it('lists every criterion tied for the lowest', () => {
    expect(weakestCriteria(bands(6.5, 6.0, 6.0, 6.5))).toEqual(['coherence', 'lexical']);
  });
  it('highlights nothing when all are equal or there are no bands', () => {
    expect(weakestCriteria(bands(6, 6, 6, 6))).toEqual([]);
    expect(weakestCriteria(null)).toEqual([]);
  });
});
