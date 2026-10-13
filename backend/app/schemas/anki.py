from typing import Optional, List, Literal
from pydantic import BaseModel, Field

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
