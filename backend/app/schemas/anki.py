from typing import Optional, List, Literal
from pydantic import BaseModel, Field

CardType = Literal["sentence", "vocab"]

class SentenceCardRequest(BaseModel):
    sentence: str = Field(..., description="English sentence")
    translation: str = Field(default="", description="Korean translation / explanation")
    deck_name: str = Field(default="1. Language::1.1. English::Sentence")
    model_name: str = Field(default="English Sentence")
    diary_date: Optional[str] = Field(default="")

class VocabCardRequest(BaseModel):
    word: str = Field(..., description="English word or idiom")
    meaning: str = Field(default="", description="Korean meaning")
    pos: Optional[str] = Field(default="", description="Part of speech")
    synonyms: Optional[str] = Field(default="", description="Synonyms")
    example: Optional[str] = Field(default="", description="Example sentence")
    explanation: Optional[str] = Field(default="", description="Usage nuance/explanation")
    deck_name: str = Field(default="1. Language::1.1. English::Vocabulary")
    model_name: str = Field(default="English Vocabulary")
    diary_date: Optional[str] = Field(default="")

class CardPreviewRequest(BaseModel):
    card_type: CardType
    text: str = Field(..., description="Sentence or word to make into card")
    context: Optional[str] = Field(default="", description="Diary context or correction info")

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

class DeleteCardRequest(BaseModel):
    card_type: Literal['sentence', 'vocab'] = Field(..., description="Type of card: sentence or vocab")
    text: str = Field(..., description="Sentence text or vocab word to delete")
