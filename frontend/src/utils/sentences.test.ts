import { describe, expect, it } from 'vitest';
import { isCompleteSentence, splitSentences } from './sentences';

const parts = (t: string) => splitSentences(t).map(([a, b]) => t.slice(a, b));

// Same cases as backend tests/test_split_sentences.py: one rule for the whole app.
describe('splitSentences', () => {
  it('splits plain sentences', () => {
    expect(parts('I like cats. They are cute! Are you sure?')).toEqual(['I like cats.', 'They are cute!', 'Are you sure?']);
  });
  it('does not end a sentence at a question quoted inside it', () => {
    const t = 'In order to answer the question "why is polarization increasing?" we should focus on the public first.';
    expect(parts(t)).toEqual([t]);
  });
  it('ends at a quoted sentence followed by a capital', () => {
    expect(parts('He asked "Why?" Then he left.')).toEqual(['He asked "Why?"', 'Then he left.']);
  });
  it.each([
    'Many countries, e.g. Korea and Japan, have this problem.',
    'Some fields, i.e. physics, need math.',
    'Mr. Kim and Dr. Lee met in the U.S. last year.',
    'The rate rose to 3.5 percent this year.',
  ])('keeps abbreviations and decimals inside: %s', (t) => {
    expect(parts(t)).toEqual([t]);
  });
  it('continues after a period followed by lowercase', () => {
    const t = 'We need food, water, etc. and we also need shelter.';
    expect(parts(t)).toEqual([t]);
  });
  it('ends at a newline even without punctuation', () => {
    expect(parts('Title line\nThe essay starts here.')).toEqual(['Title line', 'The essay starts here.']);
  });
  it('keeps a last sentence without punctuation', () => {
    expect(parts('First one. Second one')).toEqual(['First one.', 'Second one']);
  });
  it('returns spans into the original text', () => {
    expect(splitSentences('  One.  Two?  ')).toEqual([[2, 6], [8, 12]]);
  });
});

describe('isCompleteSentence', () => {
  it.each(['He goes to school.', '"Why?" she asked.', 'Is it true?', '3D printers are cheap now.'])('accepts %s', (s) => {
    expect(isCompleteSentence(s)).toBe(true);
  });
  it.each([
    ['two sentences', 'There is not much to do. On the internet, it is hard.'],
    ['starts in lowercase (a cut-off tail)', 'we should focus on the public first.'],
    ['no final punctuation', 'He goes to school'],
    ['empty', '  '],
  ])('rejects %s', (_why, s) => {
    expect(isCompleteSentence(s)).toBe(false);
  });
});
