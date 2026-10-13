import { describe, expect, it } from 'vitest';
import { SuggestionItem } from '../types/essay';
import { blankCount, grammarDraft, narrowFix } from './cardText';

const fix = (text: string, original: string, suggested: string, extra: Partial<SuggestionItem> = {}): SuggestionItem => {
  const start = text.indexOf(original);
  return {
    id: original, original_phrase: original, suggested_phrase: suggested, category: 'Grammar', subcategory: '',
    tier: 'accuracy', explanation: '', start_idx: start, end_idx: start + original.length, ...extra,
  };
};

describe('narrowFix', () => {
  it('blanks only the changed word when it is unique', () => {
    const s = 'Some events are very similar to other events.';
    expect(narrowFix(s, 'are very similar with other', 'are very similar to other')).toEqual({ answer: 'to', mistake: 'with' });
  });

  it('widens until the blank appears once', () => {
    // "to" alone appears twice
    const s = 'We went to school and are very similar to them.';
    expect(narrowFix(s, 'similar with them', 'similar to them')).toEqual({ answer: 'similar to', mistake: 'similar with' });
  });

  it('widens a pure insertion so the mistake is not empty', () => {
    const s = 'This is what technology can help with, but it is not enough.';
    expect(narrowFix(s, 'can help, but', 'can help with, but')).toEqual({ answer: 'help with', mistake: 'help' });
  });

  it('widens a pure deletion so the answer is not empty', () => {
    // the card asks "to ___ progress": make / make a / ...
    const s = 'These are not enough to make progress.';
    expect(narrowFix(s, 'to make a progress', 'to make progress')).toEqual({ answer: 'make', mistake: 'make a' });
  });

  it('ignores case differences at the edges', () => {
    const s = 'Satellites are useful, and antibiotics are cheap.';
    expect(narrowFix(s, 'satellites is useful', 'Satellites are useful')).toEqual({ answer: 'Satellites are', mistake: 'satellites is' });
  });

  it('never leaves punctuation at the blank edge (the template would not match it)', () => {
    const s = 'There are many parts, and these are important.';
    const r = narrowFix(s, 'parts, these', 'parts, and these');
    expect(blankCount(s, r.answer)).toBe(1);
    expect(r.mistake).not.toBe('');
  });

  it('falls back to the whole phrase when nothing narrower is unique', () => {
    const s = 'the the the';
    expect(narrowFix(s, 'a the', 'the the')).toEqual({ answer: 'the the', mistake: 'a the' });
  });
});

describe('grammarDraft', () => {
  it('uses the sentence with every located fix applied, not only this one', () => {
    const text = 'Science can help, but these are not enough to make a progress. Next one.';
    const a = fix(text, 'can help, but', 'can help with, but');
    const b = fix(text, 'to make a progress', 'to make progress');
    const d = grammarDraft(text, [a, b], a);
    expect(d.sentence).toBe('Science can help with, but these are not enough to make progress.');
    expect(d.answer).toBe('help with');
    expect(d.mistake).toBe('help');
  });

  it('skips fixes whose phrase no longer matches the text and style tips', () => {
    const text = 'He go to school every days.';
    const a = fix(text, 'He go', 'He goes');
    const stale = { ...fix(text, 'every days', 'every day'), start_idx: 3 };
    const style = fix(text, 'every days', 'daily', { tier: 'style' });
    const d = grammarDraft(text, [a, stale, style], a);
    expect(d.sentence).toBe('He goes to school every days.');
    expect(d.answer).toBe('goes');
  });

  it('always applies this fix even when another fix overlaps it', () => {
    const text = 'He go to school every days.';
    const wide = fix(text, 'He go to school', 'He goes to the school');
    const mine = fix(text, 'go to', 'goes to');
    const d = grammarDraft(text, [wide, mine], mine);
    expect(d.sentence).toBe('He goes to school every days.');
  });
});
