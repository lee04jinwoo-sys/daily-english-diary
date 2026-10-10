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

export type EssayType =
  | 'agree_disagree'
  | 'discuss_both'
  | 'adv_disadv'
  | 'problem_solution'
  | 'hypothetical'
  | 'free';

export type EssayCategory = 'general' | 'domain' | 'issues' | 'free';

export const ESSAY_TYPE_LABELS: Record<EssayType, string> = {
  agree_disagree: '찬반',
  discuss_both: '양쪽 견해',
  adv_disadv: '장단점',
  problem_solution: '원인·해결',
  hypothetical: '가정',
  free: '자유 주제',
};

export const CATEGORY_LABELS: Record<EssayCategory, string> = {
  general: '일반',
  domain: '내 분야',
  issues: '시사',
  free: '자유',
};

export interface CriterionScore {
  band: number;
  comment: string;
}

export interface EssayRubric {
  task_response: CriterionScore;
  coherence: CriterionScore;
  lexical: CriterionScore;
  grammar: CriterionScore;
  overall_band: number;
}

export interface ArgumentFeedback {
  thesis: string;
  strongest_point: string;
  weakest_point: string;
  missing_counterargument: string;
  paragraph_comments: Array<{ paragraph: number; comment: string }>;
}

export interface ReviewResponse {
  essay_id: string;
  original_text: string;
  corrected_text: string;
  upgraded_text: string;
  overall_feedback: string;
  rubric: EssayRubric;
  argument: ArgumentFeedback;
  revision_focus: string[];
  suggestions: SuggestionItem[];
  sentence_pairs?: SentencePair[];
  key_expressions: KeyExpression[];
}

export interface Essay {
  id: string;
  date: string;
  topic_id: string | null;
  prompt: string;
  essay_type: EssayType;
  category: EssayCategory;
  content: string;
  word_count: number;
  revision_of: string | null;
  is_reviewed: boolean;
  is_completed: boolean;
  overall_band: number | null;
  writing_seconds: number;
  review: ReviewResponse | null;
  created_at: string;
  updated_at: string;
}

export interface EssayListItem {
  id: string;
  date: string;
  prompt: string;
  essay_type: EssayType;
  category: EssayCategory;
  word_count: number;
  revision_of: string | null;
  is_reviewed: boolean;
  is_completed: boolean;
  overall_band: number | null;
  writing_seconds: number;
  preview: string;
  updated_at: string;
}

export interface EssayListResponse {
  essays: EssayListItem[];
  total_count: number;
  streak: number;
}

export interface Topic {
  id: string;
  category: EssayCategory;
  type: EssayType;
  prompt: string;
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
  essay_count: number;
  word_count: number;
  best_band: number | null;
}

export interface BandTrendItem {
  essay_id: string;
  date: string;
  essay_type: EssayType;
  revision_of: string | null;
  overall_band: number;
  task_response: number;
  coherence: number;
  lexical: number;
  grammar: number;
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
  total_essays: number;
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
  avg_band: number | null;
  band_trends: BandTrendItem[];
  type_bands: Record<string, number>;
}
