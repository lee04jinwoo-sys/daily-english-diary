// One sentence rule for the whole app; backend app/services/text_utils.py split_sentences mirrors it.
// A run of . ! ? (plus closing quotes/brackets) ends a sentence only when whitespace and then a
// non-lowercase character follow, so a question quoted inside a sentence, "3.5", "U.S. last year" or a
// title such as "Mr. Kim" do not cut it into fragments. A newline always ends a sentence.
const CLOSERS = '"\')]”’';
const ABBREVIATIONS = new Set(['mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'st', 'vs', 'e.g', 'i.e', 'cf']);
const isSpace = (c: string) => /\s/.test(c);
const isLower = (c: string) => /\p{Ll}/u.test(c);
const isLetter = (c: string) => /\p{L}/u.test(c);

function endsSentence(text: string, first: number, after: number): boolean {
  if (after >= text.length) return true;
  if (!isSpace(text[after])) return false;
  let k = after;
  while (k < text.length && isSpace(text[k])) k++;
  if (k >= text.length) return true;
  if (isLower(text[k])) return false;
  if (text[first] === '.') {
    let w = first;
    while (w > 0 && (isLetter(text[w - 1]) || text[w - 1] === '.')) w--;
    if (ABBREVIATIONS.has(text.slice(w, first).toLowerCase())) return false;
  }
  return true;
}

/** [start, end) of each sentence, whitespace trimmed. */
export function splitSentences(text: string): [number, number][] {
  const spans: [number, number][] = [];
  const add = (start: number, end: number) => {
    while (start < end && isSpace(text[start])) start++;
    while (end > start && isSpace(text[end - 1])) end--;
    if (end > start) spans.push([start, end]);
  };
  let start = 0;
  let i = 0;
  while (i < text.length) {
    if (text[i] === '\n') {
      add(start, i);
      start = i = i + 1;
    } else if ('.!?'.includes(text[i])) {
      let j = i;
      while (j < text.length && '.!?'.includes(text[j])) j++;
      while (j < text.length && CLOSERS.includes(text[j])) j++;
      if (endsSentence(text, i, j)) {
        add(start, j);
        start = j;
      }
      i = j;
    } else {
      i++;
    }
  }
  add(start, text.length);
  return spans;
}

/** Exactly one sentence that starts like a sentence and ends with . ! or ? (closing quotes allowed). */
export function isCompleteSentence(s: string): boolean {
  const t = s.trim();
  if (!t || splitSentences(t).length !== 1) return false;
  return /^["'(\[“‘]?[A-Z0-9]/.test(t) && /[.!?]["')\]”’]*$/.test(t);
}
