import { EssayListItem } from '../types/essay';

/** Words per minute, one decimal; unknown without words or at least a minute of writing time. */
export function wordsPerMinute(wordCount: number, writingSeconds: number): number | null {
  if (wordCount <= 0 || writingSeconds < 60) return null;
  return Math.round((wordCount / (writingSeconds / 60)) * 10) / 10;
}

const errorsOf = (e: EssayListItem | undefined) => e?.metrics?.errors_per_100 ?? null;

/**
 * How accuracy errors per 100 words moved (negative = fewer errors): against the essay it rewrites
 * (when that one was reviewed), else against the previous reviewed essay. `all` is newest first,
 * like the sidebar, so the previous essay is further down.
 */
export function errorDelta(essay: EssayListItem, all: EssayListItem[]): number | null {
  const now = errorsOf(essay);
  if (now == null) return null;
  const original = essay.revision_of ? all.find((e) => e.id === essay.revision_of) : undefined;
  const base =
    errorsOf(original) != null
      ? original
      : all.slice(all.findIndex((e) => e.id === essay.id) + 1).find((e) => errorsOf(e) != null);
  const before = errorsOf(base);
  if (before == null) return null;
  return Math.round((now - before) * 10) / 10;
}
