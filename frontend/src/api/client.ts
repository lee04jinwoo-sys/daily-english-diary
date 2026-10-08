import {
  Diary,
  DiaryListResponse,
  ReviewResponse,
  SuggestionItem,
  AnkiStatus,
  AnkiActionResponse,
  CardPreviewRequest,
  CardPreviewResponse,
  StatsResponse
} from '../types/diary';

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
  // Diaries
  getDiaries: () => fetchJson<DiaryListResponse>('/diaries'),
  getDiary: (date: string) => fetchJson<Diary>(`/diaries/${date}`),
  saveDiary: (data: Partial<Diary> & { date: string; content: string }) =>
    fetchJson<Diary>('/diaries', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteDiary: (date: string) =>
    fetchJson<{ success: boolean; message: string }>(`/diaries/${date}`, {
      method: 'DELETE',
    }),
  getDiarySuggestions: (date: string) =>
    fetchJson<SuggestionItem[]>(`/diaries/${date}/suggestions`),

  // Review
  reviewDiary: (data: { date: string; title?: string; content: string }) =>
    fetchJson<ReviewResponse>('/review', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

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
  launchAnki: () =>
    fetchJson<{ success: boolean; message: string }>('/anki/launch', {
      method: 'POST',
    }),
  previewAnkiCard: (req: CardPreviewRequest) =>
    fetchJson<CardPreviewResponse>('/anki/preview', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  addSentenceCard: (data: {
    sentence: string;
    translation?: string;
    deck_name?: string;
    model_name?: string;
    diary_date?: string;
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
    deck_name?: string;
    model_name?: string;
    diary_date?: string;
  }) =>
    fetchJson<AnkiActionResponse>('/anki/add-vocab', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteCard: (data: { card_type: 'sentence' | 'vocab'; text: string }) =>
    fetchJson<AnkiActionResponse>('/anki/delete-card', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  toggleDiaryComplete: (date: string) =>
    fetchJson<Diary>(`/diaries/${date}/toggle-complete`, {
      method: 'PATCH',
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
