import { SuggestionItem } from '../types/essay';

/** The learner's whole sentence (as reviewed) with one fix applied; falls back to the fix itself. */
export function correctedSentence(originalText: string, sg: SuggestionItem): string {
  if (sg.start_idx < 0 || originalText.slice(sg.start_idx, sg.end_idx) !== sg.original_phrase) return sg.suggested_phrase;
  const re = /[^.!?\n]+[.!?]*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(originalText))) {
    const start = m.index;
    const end = start + m[0].length;
    if (sg.start_idx >= start && sg.end_idx <= end) {
      return (originalText.slice(start, sg.start_idx) + sg.suggested_phrase + originalText.slice(sg.end_idx, end)).trim();
    }
  }
  return sg.suggested_phrase;
}

/** How many blanks the English Grammar card front makes: it replaces /\b<answer>\b/gi. */
export function blankCount(sentence: string, answer: string): number {
  const a = answer.trim();
  if (!a) return 0;
  const escaped = a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return (sentence.match(new RegExp('\\b' + escaped + '\\b', 'gi')) || []).length;
}

/** The sentence as the card front shows it. */
export function blankedSentence(sentence: string, answer: string): string {
  const a = answer.trim();
  if (!a) return sentence;
  const escaped = a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return sentence.replace(new RegExp('\\b' + escaped + '\\b', 'gi'), '__________');
}

export interface GrammarCardDraft {
  sentence: string;
  answer: string;
  mistake: string;
  explanation?: string;
}

const isWord = (c: string | undefined) => !!c && /[A-Za-z0-9']/.test(c);
const trimEdges = (t: string) => t.replace(/^[^A-Za-z0-9']+|[^A-Za-z0-9']+$/g, '');

/**
 * The narrowest blank that still tests the fix: only the words that changed, widened one word
 * at a time (left, then right) until the blank is non-empty on both sides and appears once in
 * the sentence. Falls back to the whole phrases.
 */
export function narrowFix(sentence: string, original: string, suggested: string): { answer: string; mistake: string } {
  const s = suggested, o = original;
  const sl = s.toLowerCase(), ol = o.toLowerCase();
  let p = 0;
  while (p < s.length && p < o.length && sl[p] === ol[p]) p++;
  let q = 0;
  while (q < s.length - p && q < o.length - p && sl[s.length - 1 - q] === ol[o.length - 1 - q]) q++;
  // never split a word
  while (p > 0 && isWord(s[p - 1]) && (isWord(s[p]) || isWord(o[p]))) p--;
  while (q > 0 && isWord(s[s.length - q]) && (isWord(s[s.length - q - 1]) || isWord(o[o.length - q - 1]))) q--;

  let start = p, endS = s.length - q;
  const pick = () => ({ answer: trimEdges(s.slice(start, endS)), mistake: trimEdges(o.slice(start, o.length - (s.length - endS))) });
  const ok = (c: { answer: string; mistake: string }) =>
    !!c.answer && !!c.mistake && c.answer.toLowerCase() !== c.mistake.toLowerCase() && blankCount(sentence, c.answer) === 1;
  const growLeft = () => {
    let i = start;
    while (i > 0 && !isWord(s[i - 1])) i--;
    while (i > 0 && isWord(s[i - 1])) i--;
    if (i === start) return false;
    start = i;
    return true;
  };
  const growRight = () => {
    let j = endS;
    while (j < s.length && !isWord(s[j])) j++;
    while (j < s.length && isWord(s[j])) j++;
    if (j === endS) return false;
    endS = j;
    return true;
  };

  for (let step = 0; ; step++) {
    const c = pick();
    if (ok(c)) return c;
    const grew = step % 2 === 0 ? growLeft() || growRight() : growRight() || growLeft();
    if (!grew) return { answer: suggested.trim(), mistake: original.trim() };
  }
}

const SENTENCE = /[^.!?\n]+(?:[.!?]+["')\]]*|$)/g;

/**
 * The learner's sentence containing this fix, with every located accuracy/idiom fix in it
 * applied (same rule as the backend's apply_suggestions), so the card holds no other mistakes.
 */
export function fullyCorrectedSentence(originalText: string, suggestions: SuggestionItem[], sg: SuggestionItem): string | null {
  if (sg.start_idx < 0 || originalText.slice(sg.start_idx, sg.end_idx) !== sg.original_phrase) return null;
  for (const m of originalText.matchAll(SENTENCE)) {
    const start = m.index!, end = start + m[0].length;
    if (sg.start_idx < start || sg.end_idx > end) continue;
    let out = '', pos = start;
    const applied = suggestions
      .filter((x) => x === sg || ((x.tier || 'accuracy') !== 'style'))
      .filter((x) => x.start_idx >= start && x.end_idx <= end && originalText.slice(x.start_idx, x.end_idx) === x.original_phrase)
      .filter((x) => x === sg || x.end_idx <= sg.start_idx || x.start_idx >= sg.end_idx) // this fix wins overlaps
      .sort((a, b) => a.start_idx - b.start_idx);
    for (const x of applied) {
      if (x.start_idx < pos) continue; // overlaps an earlier fix
      out += originalText.slice(pos, x.start_idx) + x.suggested_phrase;
      pos = x.end_idx;
    }
    return (out + originalText.slice(pos, end)).trim();
  }
  return null;
}

export function grammarDraft(originalText: string, suggestions: SuggestionItem[], sg: SuggestionItem): GrammarCardDraft {
  const sentence = fullyCorrectedSentence(originalText, suggestions, sg) ?? correctedSentence(originalText, sg);
  return { sentence, ...narrowFix(sentence, sg.original_phrase, sg.suggested_phrase), explanation: sg.explanation };
}

/** Grammar cards make sense for grammar fixes that replace one wording with another. */
export function isGrammarFix(sg: SuggestionItem): boolean {
  return sg.category === 'Grammar' && !!sg.suggested_phrase.trim();
}

export type SkipReason = 'unlocated' | 'blank' | 'same' | 'same_sentence';

export interface GrammarPlan {
  cards: GrammarCardDraft[];
  /** `draft` is set for 'same_sentence': a valid card that only shares its sentence with a chosen one. */
  skipped: { suggestion: SuggestionItem; reason: SkipReason; draft?: GrammarCardDraft }[];
}

/**
 * Every grammar card an essay can yield from the learner's own sentences, in text order. Anki treats
 * two grammar notes with the same sentence as duplicates (the first field alone decides), and a card's
 * sentence has all the sentence's fixes applied, so a sentence with several fixes gets one card: the
 * fix that belongs to a recurring pattern, else the leftmost valid one. The other valid fixes come back
 * as 'same_sentence' with their draft (they can still get a card on a new, similar sentence). Fixes that
 * cannot make a card are returned with the reason instead of being dropped silently.
 */
export function planGrammarCards(
  originalText: string,
  suggestions: SuggestionItem[],
  patterns: { examples: string[] }[] = [],
): GrammarPlan {
  const inPattern = (sg: SuggestionItem) => {
    const o = sg.original_phrase.trim().toLowerCase();
    return patterns.some((p) => p.examples.some((e) => {
      const x = e.trim().toLowerCase();
      return x.length >= 3 && o.length >= 3 && (x === o || x.includes(o) || o.includes(x));
    }));
  };
  const plan: GrammarPlan = { cards: [], skipped: [] };
  const chosen: { draft: GrammarCardDraft; start: number }[] = [];
  const taken = new Set<string>();
  const fixes = suggestions
    .filter(isGrammarFix)
    .sort((a, b) => Number(!inPattern(a)) - Number(!inPattern(b)) || a.start_idx - b.start_idx);
  for (const sg of fixes) {
    const sentence = fullyCorrectedSentence(originalText, suggestions, sg);
    if (sentence === null) {
      plan.skipped.push({ suggestion: sg, reason: 'unlocated' });
      continue;
    }
    const draft: GrammarCardDraft = {
      sentence, ...narrowFix(sentence, sg.original_phrase, sg.suggested_phrase), explanation: sg.explanation,
    };
    if (!draft.mistake.trim() || draft.mistake.trim().toLowerCase() === draft.answer.trim().toLowerCase()) {
      plan.skipped.push({ suggestion: sg, reason: 'same' });
    } else if (blankCount(draft.sentence, draft.answer) !== 1) {
      plan.skipped.push({ suggestion: sg, reason: 'blank' });
    } else {
      const key = sentence.toLowerCase().replace(/\s+/g, ' ').trim();
      if (taken.has(key)) {
        plan.skipped.push({ suggestion: sg, reason: 'same_sentence', draft });
      } else {
        taken.add(key);
        chosen.push({ draft, start: sg.start_idx });
      }
    }
  }
  plan.cards = chosen.sort((a, b) => a.start - b.start).map((c) => c.draft);
  return plan;
}
