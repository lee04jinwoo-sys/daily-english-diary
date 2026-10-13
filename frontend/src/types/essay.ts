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
  | 'two_part'
  | 'hypothetical'
  | 'free';

// general/domain/issues: essays from the earlier hand-made bank; new bank topics are 'ielts'.
export type EssayCategory = 'ielts' | 'general' | 'domain' | 'issues' | 'free';

export const ESSAY_TYPE_LABELS: Record<EssayType, string> = {
  agree_disagree: '찬반',
  discuss_both: '양쪽 견해',
  adv_disadv: '장단점',
  problem_solution: '원인·해결',
  two_part: '두 질문',
  hypothetical: '가정',
  free: '자유 주제',
};

export const CATEGORY_LABELS: Record<EssayCategory, string> = {
  ielts: 'IELTS 기출',
  general: '일반',
  domain: '내 분야',
  issues: '시사',
  free: '자유',
};

export const THEME_LABELS: Record<string, string> = {
  education: '교육', technology: '기술', work: '일·직업', environment: '환경', health: '건강',
  society: '사회', government: '정부·정책', crime: '범죄', culture: '문화', family: '가족',
  media: '미디어', transport: '교통', economy: '경제', science: '과학', travel: '여행', sport: '스포츠',
};

export interface CriterionScore {
  band: number;
  comment: string;
  spread?: number; // max - min band across the scoring runs
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

export interface RecurringPattern {
  pattern: string;
  count: number;
  examples: string[];
  fix: string;
  tip: string;
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
  recurring_patterns?: RecurringPattern[];
  suggestions: SuggestionItem[];
  sentence_pairs?: SentencePair[];
  key_expressions: KeyExpression[];
  suggestions_verified?: boolean;
}

// Parts of a streamed review, in roughly the order they arrive.
export type ReviewPart = 'content_scores' | 'feedback' | 'corrections' | 'language_scores';
export const REVIEW_PARTS: ReviewPart[] = ['content_scores', 'feedback', 'corrections', 'language_scores'];

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
  theme?: string | null;
  essays?: number; // test takers in the source dataset who wrote on it
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
  /** ok | tunnel_down (SSH tunnel to the Oracle server) | anki_down (server Anki) */
  reason?: 'ok' | 'tunnel_down' | 'anki_down';
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
  number: number;
  date: string;
  essay_type: EssayType;
  revision_of: string | null;
  overall_band: number;
  task_response: number;
  coherence: number;
  lexical: number;
  grammar: number;
}

// One reviewed essay; number is its place in writing order among essays with text.
export interface EssayTrendItem {
  essay_id: string;
  number: number;
  date: string;
  essay_type: EssayType;
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
  essay_trends?: EssayTrendItem[];
  avg_band: number | null;
  band_trends: BandTrendItem[];
  type_bands: Record<string, number>;
  writing_trends?: WritingTrendItem[];
}

export type WritingSignal = 'improving' | 'rushed' | 'careful' | 'declining' | 'slower' | 'steady';

// Speed next to accuracy for one reviewed essay with a recorded writing time.
export interface WritingTrendItem {
  essay_id: string;
  number: number;
  date: string;
  essay_type: EssayType;
  is_revision: boolean;
  word_count: number;
  minutes: number;
  wpm: number;
  error_density: number;
  accuracy_density: number;
  signal: WritingSignal | null;
}
