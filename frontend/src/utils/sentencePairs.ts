export type PairsState = 'idle' | 'loading' | 'error';

export interface PrefetchCheck {
  hasReview: boolean;
  isReviewing: boolean;
  storedCount: number;
  hasLazyPairs: boolean;
  pairsState: PairsState;
}

export function shouldPrefetchSentencePairs({
  hasReview,
  isReviewing,
  storedCount,
  hasLazyPairs,
  pairsState,
}: PrefetchCheck): boolean {
  return hasReview && !isReviewing && storedCount === 0 && !hasLazyPairs && pairsState === 'idle';
}
