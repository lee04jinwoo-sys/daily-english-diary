import { describe, expect, it } from 'vitest';
import { EssayListItem } from '../types/essay';
import { errorDelta, wordsPerMinute } from './essaySummary';

// the list is newest first, like the sidebar; `errors` = accuracy errors per 100 words (null = not reviewed)
const metrics = (errors: number) => ({
  words: 300, sentences: 15, accuracy_errors: 0, errors_per_100: errors, clean_sentences: 5, clean_sentence_pct: 33, awkward: 0,
});
const essay = (id: string, errors: number | null, extra: Partial<EssayListItem> = {}): EssayListItem => ({
  id, date: '2026-11-01', prompt: 'p', essay_type: 'free', category: 'free', word_count: 300, revision_of: null,
  is_reviewed: errors != null, is_completed: false, writing_seconds: 0, preview: '', updated_at: '',
  metrics: errors == null ? null : metrics(errors), correction_count: 0, grammar_count: 0, ...extra,
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

describe('errorDelta', () => {
  it('compares with the previous reviewed essay (the next one down in a newest-first list)', () => {
    const list = [essay('c', 4.0), essay('b', null), essay('a', 5.5)];
    expect(errorDelta(list[0], list)).toBe(-1.5); // fewer errors; skips the unreviewed one
  });
  it('is positive when errors went up and zero when they did not change', () => {
    const list = [essay('c', 6.0), essay('b', 5.0), essay('a', 5.0)];
    expect(errorDelta(list[0], list)).toBe(1);
    expect(errorDelta(list[1], list)).toBe(0);
  });
  it('has nothing to compare for the first reviewed essay or an unreviewed one', () => {
    const list = [essay('b', null), essay('a', 5.0)];
    expect(errorDelta(list[0], list)).toBeNull();
    expect(errorDelta(list[1], list)).toBeNull();
  });
  it('compares a rewrite with the essay it rewrites, not with the previous essay', () => {
    const list = [essay('rew', 2.0, { revision_of: 'orig' }), essay('other', 9.0), essay('orig', 5.0)];
    expect(errorDelta(list[0], list)).toBe(-3);
  });
  it('falls back to the previous essay when the original was not reviewed', () => {
    const list = [essay('rew', 4.0, { revision_of: 'orig' }), essay('prev', 4.5), essay('orig', null)];
    expect(errorDelta(list[0], list)).toBe(-0.5);
  });
  it('does not accumulate float noise', () => {
    const list = [essay('b', 4.7), essay('a', 4.4)];
    expect(errorDelta(list[0], list)).toBe(0.3);
  });
});
