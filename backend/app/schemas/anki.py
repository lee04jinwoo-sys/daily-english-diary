import re
from typing import Dict, Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

CardType = Literal["sentence", "vocab"]

class SentenceCardRequest(BaseModel):
    sentence: str = Field(..., description="English sentence")
    translation: str = Field(default="", description="Natural Korean translation only (Anki Manager rule)")

class VocabCardRequest(BaseModel):
    word: str = Field(..., description="English word or idiom")
    meaning: str = Field(default="", description="Korean meaning")
    pos: Optional[str] = Field(default="", description="Part of speech")
    # Accepted for compatibility but not forwarded: the Anki Manager gateway writes
    # example and explanation under its own rules and always leaves synonyms empty.
    synonyms: Optional[str] = Field(default="", description="Ignored")
    example: Optional[str] = Field(default="", description="Ignored")
    explanation: Optional[str] = Field(default="", description="Ignored")

class GrammarCardRequest(BaseModel):
    sentence: str = Field(..., description="Corrected full sentence")
    answer: str = Field(..., description="The corrected phrase; blanked on the card front")
    mistake: str = Field(default="", description="What the learner actually wrote; kept as a wrong option")
    essay_id: Optional[str] = Field(default=None, description="Essay the card comes from; becomes a tag")
    fix_id: Optional[str] = Field(default=None, description="Correction the card tests; becomes a tag")
    translation: str = Field(default="", description="Checked Korean translation; empty lets Anki Manager write one")
    distractors: List[str] = Field(default_factory=list, description="Checked wrong options (Sonnet), sent after my mistake")

    @field_validator("essay_id", "fix_id")
    @classmethod
    def _tag_safe(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v):
            raise ValueError("id must be 1-64 letters, digits, '-' or '_'")
        return v

class CardPreviewRequest(BaseModel):
    card_type: CardType
    text: str = Field(..., description="Sentence or word to make into card")
    context: Optional[str] = Field(default="", description="Essay context or correction info")

class CardPreviewResponse(BaseModel):
    card_type: CardType
    deck_name: str
    model_name: str
    front: str
    meaning: str
    explanation: str
    example: str
    pos: str
    synonyms: str

class SimilarItem(BaseModel):
    id: str
    answer: str
    mistake: str = ""
    sentence: str

class SimilarSentencesRequest(BaseModel):
    items: List[SimilarItem]

class SimilarSentencesResponse(BaseModel):
    sentences: Dict[str, str]

class CardDraftItem(BaseModel):
    id: str
    sentence: str
    answer: str
    mistake: str = ""

class PrepareGrammarCardsRequest(BaseModel):
    items: List[CardDraftItem]

class PreparedCard(BaseModel):
    sentence: str
    translation: str
    distractors: List[str] = Field(default_factory=list)

class PrepareGrammarCardsResponse(BaseModel):
    cards: Dict[str, PreparedCard]
    rejected: Dict[str, str]

class GrammarRegisteredResponse(BaseModel):
    fix_ids: List[str]

class UndoCardRequest(BaseModel):
    note_id: int

class AnkiActionResponse(BaseModel):
    success: bool
    note_id: Optional[int] = None
    error: Optional[str] = None
    duplicate: bool = False
    message: Optional[str] = None

class AnkiStatusResponse(BaseModel):
    connected: bool
    reason: str = "ok"  # ok | tunnel_down (SSH tunnel to the server) | anki_down (server Anki)
    anki_url: str
    sentence_deck: str
    vocab_deck: str
    available_decks: List[str] = Field(default_factory=list)

class CheckExistingCardsRequest(BaseModel):
    sentences: List[str] = Field(default_factory=list)
    words: List[str] = Field(default_factory=list)

class CheckExistingCardsResponse(BaseModel):
    existing_sentences: List[str] = Field(default_factory=list)
    existing_words: List[str] = Field(default_factory=list)
