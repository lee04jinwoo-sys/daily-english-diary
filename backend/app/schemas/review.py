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
    essay_id: str = Field(..., description="Essay being reviewed")
    content: str = Field(..., min_length=5, description="Essay text to be reviewed")


class CriterionScore(BaseModel):
    band: float = Field(..., description="IELTS-style band 0-9 in 0.5 steps")
    comment: str = Field(default="", description="One-line Korean comment")


class EssayRubric(BaseModel):
    task_response: CriterionScore
    coherence: CriterionScore
    lexical: CriterionScore
    grammar: CriterionScore
    overall_band: float


class ParagraphComment(BaseModel):
    paragraph: int
    comment: str


class ArgumentFeedback(BaseModel):
    thesis: str = Field(default="", description="How clear and arguable the position is")
    strongest_point: str = ""
    weakest_point: str = Field(default="", description="Weakest argument and how to strengthen it")
    missing_counterargument: str = Field(default="", description="Counterargument the essay should address")
    paragraph_comments: List[ParagraphComment] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    essay_id: str
    original_text: str
    corrected_text: str = Field(..., description="Minimal grammar/spelling fixes, user's structure kept")
    upgraded_text: str = Field(..., description="Same argument rewritten at C1+ level")
    overall_feedback: str
    rubric: EssayRubric
    argument: ArgumentFeedback
    revision_focus: List[str] = Field(default_factory=list, description="2-3 things to fix when rewriting")
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    sentence_pairs: List[SentencePair] = Field(default_factory=list)
    key_expressions: List[KeyExpression] = Field(default_factory=list)
