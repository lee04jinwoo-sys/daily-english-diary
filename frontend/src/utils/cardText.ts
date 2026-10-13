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

export function grammarDraft(originalText: string, sg: SuggestionItem): GrammarCardDraft {
  return {
    sentence: correctedSentence(originalText, sg),
    answer: sg.suggested_phrase,
    mistake: sg.original_phrase,
    explanation: sg.explanation,
  };
}

/** Grammar cards make sense for grammar fixes that replace one wording with another. */
export function isGrammarFix(sg: SuggestionItem): boolean {
  return sg.category === 'Grammar' && !!sg.suggested_phrase.trim();
}
