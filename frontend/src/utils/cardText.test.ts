import { describe, expect, it } from 'vitest';
import { SuggestionItem } from '../types/essay';
import { blankCount, grammarDraft, narrowFix, planGrammarCards } from './cardText';

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


describe('planGrammarCards', () => {
  const TEXT = 'He go to school every day. I like cats. Many people works long hours and they is tired.';

  it('makes one card per grammar fix, in text order, each with exactly one blank', () => {
    const sugg = [
      fix(TEXT, 'Many people works', 'Many people work', { id: 'b' }),
      fix(TEXT, 'He go', 'He goes', { id: 'a' }),
    ];
    const plan = planGrammarCards(TEXT, sugg);
    expect(plan.skipped).toEqual([]);
    expect(plan.cards.length).toBe(2);
    expect(plan.cards[0].sentence).toBe('He goes to school every day.');
    for (const c of plan.cards) expect(blankCount(c.sentence, c.answer)).toBe(1);
  });

  it('leaves out fixes that are not grammar fixes', () => {
    const sugg = [
      fix(TEXT, 'He go', 'He goes'),
      fix(TEXT, 'I like cats', 'I adore cats', { category: 'Vocabulary' }),
      fix(TEXT, 'I like cats', '', { category: 'Grammar', id: 'deletion' }),
    ];
    const plan = planGrammarCards(TEXT, sugg);
    expect(plan.cards.length).toBe(1);
    expect(plan.skipped).toEqual([]); // not grammar fixes: not candidates, so not "skipped" either
  });

  it('skips a fix whose position no longer matches the text', () => {
    const lost = fix(TEXT, 'He go', 'He goes', { start_idx: 5, end_idx: 10 });
    const plan = planGrammarCards(TEXT, [lost]);
    expect(plan.cards).toEqual([]);
    expect(plan.skipped.map((s) => s.reason)).toEqual(['unlocated']);
  });

  it('skips a fix that differs only by letter case (the blank and the wrong option would be equal)', () => {
    const t = 'i agree. We left.';
    const plan = planGrammarCards(t, [fix(t, 'i', 'I')]);
    expect(plan.cards).toEqual([]);
    expect(plan.skipped.map((s) => s.reason)).toEqual(['same']);
  });

  it('keeps one card per sentence because Anki treats the same sentence as a duplicate', () => {
    const sugg = [
      fix(TEXT, 'they is', 'they are', { id: 'second' }),
      fix(TEXT, 'Many people works', 'Many people work', { id: 'first' }),
    ];
    const plan = planGrammarCards(TEXT, sugg);
    expect(plan.cards.length).toBe(1);
    expect(plan.cards[0].mistake.toLowerCase()).toContain('works'); // the leftmost fix wins
    expect(plan.skipped.map((s) => [s.suggestion.id, s.reason])).toEqual([['second', 'same_sentence']]);
    // both fixes are applied in that one sentence, so the card holds no other mistake
    expect(plan.cards[0].sentence).toBe('Many people work long hours and they are tired.');
  });

  it('prefers the fix that belongs to a recurring pattern over the leftmost one', () => {
    const sugg = [
      fix(TEXT, 'Many people works', 'Many people work', { id: 'first' }),
      fix(TEXT, 'they is', 'they are', { id: 'habit' }),
    ];
    const plan = planGrammarCards(TEXT, sugg, [{ examples: ['they is', 'it are'] }]);
    expect(plan.cards.length).toBe(1);
    expect(plan.cards[0].mistake.toLowerCase()).toContain('is');
    expect(plan.skipped.map((s) => s.suggestion.id)).toEqual(['first']);
  });

  it('keeps the cards in text order even when a later fix wins its sentence', () => {
    const sugg = [
      fix(TEXT, 'He go', 'He goes', { id: 'early' }),
      fix(TEXT, 'Many people works', 'Many people work', { id: 'a' }),
      fix(TEXT, 'they is', 'they are', { id: 'b' }),
    ];
    const plan = planGrammarCards(TEXT, sugg, [{ examples: ['they is'] }]);
    expect(plan.cards.map((c) => c.sentence)).toEqual([
      'He goes to school every day.',
      'Many people work long hours and they are tired.',
    ]);
  });

  it('hands the skipped same-sentence fix back as a usable draft (for a similar sentence)', () => {
    const sugg = [
      fix(TEXT, 'Many people works', 'Many people work', { id: 'first', explanation: '수일치' }),
      fix(TEXT, 'they is', 'they are', { id: 'second', explanation: '복수 동사' }),
    ];
    const [skip] = planGrammarCards(TEXT, sugg).skipped;
    expect(skip.reason).toBe('same_sentence');
    expect(skip.draft).toMatchObject({ answer: 'are', mistake: 'is', explanation: '복수 동사' });
    expect(skip.draft!.sentence).toBe('Many people work long hours and they are tired.');
  });

  it('puts the fix id on each draft so the card can be tagged and tracked', () => {
    const plan = planGrammarCards(TEXT, [fix(TEXT, 'He go', 'He goes', { id: 'fx1' })]);
    expect(plan.cards[0].fixId).toBe('fx1');
  });

  it('leaves out fixes that already have a card and reports them as registered', () => {
    const sugg = [fix(TEXT, 'He go', 'He goes', { id: 'a' }), fix(TEXT, 'Many people works', 'Many people work', { id: 'b' })];
    const plan = planGrammarCards(TEXT, sugg, [], new Set(['a']));
    expect(plan.cards.map((c) => c.fixId)).toEqual(['b']);
    expect(plan.registered).toEqual(['a']);
    expect(plan.skipped).toEqual([]);
  });

  it('a registered card owns its sentence: the other fix of that sentence becomes a similar-sentence candidate', () => {
    const sugg = [fix(TEXT, 'Many people works', 'Many people work', { id: 'first' }), fix(TEXT, 'they is', 'they are', { id: 'second' })];
    const plan = planGrammarCards(TEXT, sugg, [], new Set(['first']));
    expect(plan.cards).toEqual([]);
    expect(plan.registered).toEqual(['first']);
    expect(plan.skipped.map((s) => [s.suggestion.id, s.reason])).toEqual([['second', 'same_sentence']]);
    expect(plan.skipped[0].draft?.fixId).toBe('second');
  });

  it('ignores registered ids that are not fixes of this essay', () => {
    const plan = planGrammarCards(TEXT, [fix(TEXT, 'He go', 'He goes', { id: 'a' })], [], new Set(['zzz']));
    expect(plan.cards.length).toBe(1);
    expect(plan.registered).toEqual([]);
  });

  it('returns nothing for an essay without grammar fixes', () => {
    expect(planGrammarCards(TEXT, [])).toEqual({ cards: [], skipped: [], registered: [] });
  });
});
