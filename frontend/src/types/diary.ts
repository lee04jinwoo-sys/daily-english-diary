export type SuggestionCategory = 
  | 'Grammar'
  | 'Spelling'
  | 'Clarity'
  | 'Natural Expression'
  | 'Vocabulary';

export interface SuggestionItem {
  id: string;
  original_phrase: string;
  suggested_phrase: string;
  category: SuggestionCategory;
  subcategory: string;
  tier?: 'accuracy' | 'idiom' | 'style';
  explanation: string;
  start_idx: number;
  end_idx: number;
  is_applied?: boolean;
}

export interface KeyExpression {
  expression: string;
  meaning: string;
  example: string;
  pos?: string;
  synonyms?: string;
  explanation?: string;
}

export interface VocabItem {
  word: string;
  meaning: string;
  pos?: string;
}

export interface SentencePair {
  id: string;
  index: number;
  original: string;
  corrected: string;
  native: string;
  translation: string;
  explanation: string;
  vocab: VocabItem[];
}

export interface ReviewResponse {
  date: string;
  original_text: string;
  corrected_text: string;
  native_text: string;
  overall_feedback: string;
  followup_question: string;
  score: number;
  suggestions: SuggestionItem[];
  sentence_pairs?: SentencePair[];
  key_expressions: KeyExpression[];
}

export interface Diary {
  id: string;
  date: string;
  title: string;
  content: string;
  corrected_content: string;
  native_content: string;
  overall_feedback: string;
  grammar_score: number;
  word_count: number;
  is_draft: boolean;
  is_completed: boolean;
  sentence_pairs?: SentencePair[];
  key_expressions?: KeyExpression[];
  created_at: string;
  updated_at: string;
}

export interface DiaryListItem {
  id: string;
  date: string;
  title: string;
  word_count: number;
  grammar_score: number;
  is_draft: boolean;
  is_completed: boolean;
  preview: string;
  updated_at: string;
}

export interface DiaryListResponse {
  diaries: DiaryListItem[];
  total_count: number;
  streak: number;
}

export type CardType = 'sentence' | 'vocab';

export interface CardPreviewRequest {
  card_type: CardType;
  text: string;
  context?: string;
}

export interface CardPreviewResponse {
  card_type: CardType;
  deck_name: string;
  model_name: string;
  front: string;
  meaning: string;
  explanation: string;
  example: string;
  pos: string;
  synonyms: string;
}

export interface AnkiStatus {
  connected: boolean;
  anki_url: string;
  sentence_deck: string;
  vocab_deck: string;
  available_decks: string[];
}

export interface AnkiActionResponse {
  success: boolean;
  note_id?: number;
  error?: string;
  duplicate: boolean;
  message?: string;
}

export interface MistakeSample {
  category: string;
  subcategory: string;
  count: number;
  examples: Array<{
    original: string;
    suggested: string;
    explanation: string;
  }>;
}

export interface DailyActivity {
  date: string;
  has_diary: boolean;
  word_count: number;
  score: number;
  is_draft: boolean;
}

export interface DailyTrendItem {
  date: string;
  word_count: number;
  sentence_count: number;
  error_count: number;
  error_density: number;
  accuracy_density?: number;
  idiom_density?: number;
  style_density?: number;
  nci: number;
}

export interface StatsResponse {
  total_diaries: number;
  current_streak: number;
  max_streak: number;
  total_words: number;
  total_sentences: number;
  total_errors: number;
  avg_error_density: number;
  avg_accuracy_density?: number;
  avg_idiom_density?: number;
  avg_style_density?: number;
  avg_nci: number;
  category_counts: Record<string, number>;
  top_subcategories: MistakeSample[];
  daily_activity: Record<string, DailyActivity>;
  daily_trends?: DailyTrendItem[];
}
