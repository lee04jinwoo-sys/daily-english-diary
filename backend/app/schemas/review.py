from typing import List, Literal, Optional
from pydantic import BaseModel, Field

SuggestionCategory = Literal[
    "Grammar",
    "Spelling",
    "Clarity",
    "Natural Expression",
    "Vocabulary"
]

class KeyExpression(BaseModel):
    expression: str = Field(..., description="Key English expression or word (normalized A, B, V-ing)")
    meaning: str = Field(..., description="Korean meaning")
    pos: Optional[str] = Field(default="idiom", description="Part of speech: n, v, adj, adv, idiom, prep, conj")
    synonyms: Optional[str] = Field(default="", description="2~3 synonyms separated by comma")
    example: str = Field(..., description="Pure English example sentence without Korean notes")
    explanation: Optional[str] = Field(default="", description="Anki Manager 3-step explanation formula")

class VocabItem(BaseModel):
    word: str = Field(..., description="English word or idiom")
    meaning: str = Field(..., description="Korean meaning")
    pos: Optional[str] = Field(default="", description="Part of speech")

class SentencePair(BaseModel):
    id: str = Field(..., description="Sentence index ID (e.g. S1, S2)")
    index: int = Field(..., description="Sentence order 1-indexed")
    original: str = Field(..., description="User's original draft sentence")
    corrected: str = Field(default="", description="Minimal grammar/spelling fix maintaining user's tone and structure")
    native: str = Field(..., description="Native natural paraphrased sentence")
    translation: str = Field(..., description="Natural Korean translation")
    explanation: str = Field(..., description="Key grammar / expression nuance explanation in Korean")
    vocab: List[VocabItem] = Field(default_factory=list, description="Key vocabulary from this sentence")

SuggestionTier = Literal["accuracy", "idiom", "style"]

class SuggestionItem(BaseModel):
    id: Optional[str] = Field(default=None, description="Unique identifier for frontend tracking")
    original_phrase: str = Field(..., description="Exact original substring from text that needs improvement")
    suggested_phrase: str = Field(..., description="Recommended replacement text")
    category: SuggestionCategory = Field(..., description="High-level category")
    subcategory: str = Field(..., description="Detailed subcategory e.g. 시제(Tense), 전치사(Preposition), 관사(Article), 어휘(Vocabulary), 수일치(Subject-Verb), 어순(Word Order)")
    tier: SuggestionTier = Field(default="accuracy", description="3-Tier severity: accuracy (must-fix), idiom (natural polish), style (optional flair)")
    explanation: str = Field(..., description="Helpful and friendly explanation in Korean")
    start_idx: int = Field(default=-1, description="Start char offset in original text")
    end_idx: int = Field(default=-1, description="End char offset in original text")
    is_applied: bool = Field(default=False, description="Whether this suggestion has been applied")

class ReviewRequest(BaseModel):
    date: str = Field(..., description="Diary date YYYY-MM-DD")
    title: Optional[str] = Field(default="", description="Diary title")
    content: str = Field(..., min_length=5, description="Diary content to be reviewed")

class RubricScores(BaseModel):
    grammar: str = Field(default="A", description="Grammar accuracy grade: A, B, C, D, E")
    vocabulary: str = Field(default="A", description="Vocabulary variety grade: A, B, C, D, E")
    naturalness: str = Field(default="A", description="Natural expression & idiom grade: A, B, C, D, E")
    clarity: str = Field(default="A", description="Sentence complexity & clarity grade: A, B, C, D, E")
    overall_grade: str = Field(default="A", description="Overall composite grade: A+, A, B, C, D, E")

class ReviewResponse(BaseModel):
    date: str
    original_text: str
    corrected_text: str = Field(..., description="Full text with all grammatical and spelling corrections applied")
    native_text: str = Field(..., description="Polished, natural native-like paraphrased full version")
    overall_feedback: str = Field(..., description="Encouraging feedback and warm commentary on diary contents in Korean")
    followup_question: str = Field(..., description="A friendly follow-up question in English related to what happened today")
    score: int = Field(default=100, description="Overall grammar accuracy and naturalness score (0-100)")
    rubric: Optional[RubricScores] = Field(default=None, description="4-pillar rubric evaluation grades")
    suggestions: List[SuggestionItem] = Field(default_factory=list, description="List of granular inline suggestions")
    sentence_pairs: List[SentencePair] = Field(default_factory=list, description="Sentence-by-sentence comparison pairs")
    key_expressions: List[KeyExpression] = Field(default_factory=list, description="Useful expressions/vocab extracted for learning")
