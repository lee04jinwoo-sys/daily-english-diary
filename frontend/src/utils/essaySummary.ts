import { EssayListItem } from '../types/essay';

export type CriterionKey = 'task_response' | 'coherence' | 'lexical' | 'grammar';

export const CRITERIA: { key: CriterionKey; label: string }[] = [
  { key: 'task_response', label: '과제' },
  { key: 'coherence', label: '일관' },
  { key: 'lexical', label: '어휘' },
  { key: 'grammar', label: '문법' },
];

/** Words per minute, one decimal; unknown without words or at least a minute of writing time. */
export function wordsPerMinute(wordCount: number, writingSeconds: number): number | null {
  if (wordCount <= 0 || writingSeconds < 60) return null;
  return Math.round((wordCount / (writingSeconds / 60)) * 10) / 10;
}

/**
 * How the band moved: against the essay it rewrites (when that one has a band), else against the
 * previous reviewed essay. `all` is newest first, like the sidebar, so the previous essay is further down.
 */
export function bandDelta(essay: EssayListItem, all: EssayListItem[]): number | null {
  if (essay.overall_band == null) return null;
  const original = essay.revision_of ? all.find((e) => e.id === essay.revision_of) : undefined;
  const base =
    original && original.overall_band != null
      ? original
      : all.slice(all.findIndex((e) => e.id === essay.id) + 1).find((e) => e.overall_band != null);
  if (!base || base.overall_band == null) return null;
  return Math.round((essay.overall_band - base.overall_band) * 10) / 10;
}

/** The criteria tied for the lowest band; none when all are equal or there are no bands. */
export function weakestCriteria(bands: Record<CriterionKey, number> | null): CriterionKey[] {
  if (!bands) return [];
  const values = CRITERIA.map((c) => bands[c.key]);
  const min = Math.min(...values);
  if (min === Math.max(...values)) return [];
  return CRITERIA.filter((c) => bands[c.key] === min).map((c) => c.key);
}
