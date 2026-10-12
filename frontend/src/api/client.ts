import {
  Essay,
  EssayListResponse,
  EssayType,
  EssayCategory,
  Topic,
  ReviewResponse,
  ReviewPart,
  SentencePair,
  SuggestionItem,
  AnkiStatus,
  AnkiActionResponse,
  CardPreviewRequest,
  CardPreviewResponse,
  StatsResponse
} from '../types/essay';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let errorMsg = `HTTP error ${res.status}`;
    try {
      const errData = await res.json();
      if (errData.detail) errorMsg = errData.detail;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  // Essays
  getEssays: () => fetchJson<EssayListResponse>('/essays'),
  getEssay: (id: string) => fetchJson<Essay>(`/essays/${id}`),
  createEssay: (data: { prompt: string; essay_type: EssayType; category?: EssayCategory; topic_id?: string | null }) =>
    fetchJson<Essay>('/essays', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateEssay: (id: string, data: { content?: string; prompt?: string; writing_seconds?: number }, keepalive = false) =>
    fetchJson<Essay>(`/essays/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
      keepalive,
    }),
  reviseEssay: (id: string) =>
    fetchJson<Essay>(`/essays/${id}/revise`, { method: 'POST' }),
  deleteEssay: (id: string) =>
    fetchJson<{ success: boolean }>(`/essays/${id}`, { method: 'DELETE' }),
  toggleEssayComplete: (id: string) =>
    fetchJson<Essay>(`/essays/${id}/toggle-complete`, { method: 'PATCH' }),
  getEssaySuggestions: (id: string) =>
    fetchJson<SuggestionItem[]>(`/essays/${id}/suggestions`),

  getSentencePairs: (id: string) =>
    fetchJson<SentencePair[]>(`/essays/${id}/sentence-pairs`, { method: 'POST' }),

  // Topics
  suggestTopic: (exclude: string[] = []) =>
    fetchJson<Topic>(`/topics/suggest${exclude.length ? `?exclude=${encodeURIComponent(exclude.join(','))}` : ''}`),

  // Review
  reviewEssay: (data: { essay_id: string; content: string }) =>
    fetchJson<ReviewResponse>('/review', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Streamed review: onPart is called as each part arrives; resolves with the saved review.
  reviewEssayStream: async (
    data: { essay_id: string; content: string },
    onPart: (part: ReviewPart, payload: any) => void,
  ): Promise<ReviewResponse> => {
    const res = await fetch(`${API_BASE}/review/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok || !res.body) {
      let errorMsg = `HTTP error ${res.status}`;
      try {
        const errData = await res.json();
        if (errData.detail) errorMsg = errData.detail;
      } catch {
        // fallback
      }
      throw new Error(errorMsg);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let review: ReviewResponse | null = null;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (!line) continue;
        const msg = JSON.parse(line);
        if (msg.event === 'error') throw new Error(msg.detail);
        if (msg.event === 'done') review = msg.data;
        else onPart(msg.event as ReviewPart, msg.data);
      }
    }
    if (!review) throw new Error('첨삭 응답이 중간에 끊겼습니다. 다시 시도해주세요.');
    return review;
  },

  // Dictionary lookup for word popover
  lookupWord: (word: string, context: string = '') =>
    fetchJson<{
      word: string;
      phonetic: string;
      pos: string;
      meaning: string;
      explanation: string;
      synonyms: string;
      example: string;
    }>('/dict/lookup', {
      method: 'POST',
      body: JSON.stringify({ word, context }),
    }),

  // Anki
  getAnkiStatus: () => fetchJson<AnkiStatus>('/anki/status'),
  previewAnkiCard: (req: CardPreviewRequest) =>
    fetchJson<CardPreviewResponse>('/anki/preview', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  addSentenceCard: (data: {
    sentence: string;
    translation?: string;
  }) =>
    fetchJson<AnkiActionResponse>('/anki/add-sentence', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  addVocabCard: (data: {
    word: string;
    meaning?: string;
    pos?: string;
    synonyms?: string;
    example?: string;
    explanation?: string;
  }) =>
    fetchJson<AnkiActionResponse>('/anki/add-vocab', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  // Stats
  getStats: () => fetchJson<StatsResponse>('/stats'),

  // Anki card existence check
  checkExistingCards: (data: { sentences: string[]; words: string[] }) =>
    fetchJson<{ existing_sentences: string[]; existing_words: string[] }>('/anki/check-existing', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
