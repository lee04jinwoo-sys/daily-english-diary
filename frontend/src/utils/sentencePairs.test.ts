import { describe, expect, it } from 'vitest';
import { shouldPrefetchSentencePairs } from './sentencePairs';

describe('shouldPrefetchSentencePairs', () => {
  it('returns true as soon as a review exists without stored pairs, regardless of active tab', () => {
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: false,
        storedCount: 0,
        hasLazyPairs: false,
        pairsState: 'idle',
      })
    ).toBe(true);
  });

  it('returns false while review is still streaming', () => {
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: true,
        storedCount: 0,
        hasLazyPairs: false,
        pairsState: 'idle',
      })
    ).toBe(false);
  });

  it('returns false when pairs are already stored, fetched, loading, or errored', () => {
    expect(
      shouldPrefetchSentencePairs({
        hasReview: false,
        isReviewing: false,
        storedCount: 0,
        hasLazyPairs: false,
        pairsState: 'idle',
      })
    ).toBe(false);
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: false,
        storedCount: 3,
        hasLazyPairs: false,
        pairsState: 'idle',
      })
    ).toBe(false);
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: false,
        storedCount: 0,
        hasLazyPairs: true,
        pairsState: 'idle',
      })
    ).toBe(false);
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: false,
        storedCount: 0,
        hasLazyPairs: false,
        pairsState: 'loading',
      })
    ).toBe(false);
    expect(
      shouldPrefetchSentencePairs({
        hasReview: true,
        isReviewing: false,
        storedCount: 0,
        hasLazyPairs: false,
        pairsState: 'error',
      })
    ).toBe(false);
  });
});
