from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.review import SentencePair, KeyExpression

class DiaryBase(BaseModel):
    date: str = Field(..., description="Diary date in YYYY-MM-DD format")
    title: str = Field(default="", description="Diary title")
    content: str = Field(default="", description="User written diary content in English")

class DiarySaveRequest(DiaryBase):
    is_draft: bool = Field(default=False, description="Whether this is an auto-saved draft")
    is_completed: Optional[bool] = Field(default=False, description="Whether this diary is marked as completed")
    corrected_content: Optional[str] = Field(default="", description="Corrected text")
    native_content: Optional[str] = Field(default="", description="Native paraphrased text")
    overall_feedback: Optional[str] = Field(default="", description="AI feedback commentary")
    grammar_score: Optional[int] = Field(default=100, description="Overall grammar/clarity score (0-100)")
    sentence_pairs: Optional[List[SentencePair]] = Field(default_factory=list, description="Sentence 1:1 study pairs")
    key_expressions: Optional[List[KeyExpression]] = Field(default_factory=list, description="Key expressions")

class DiaryResponse(DiaryBase):
    id: str
    corrected_content: str = ""
    native_content: str = ""
    overall_feedback: str = ""
    grammar_score: int = 100
    word_count: int = 0
    is_draft: bool = False
    is_completed: bool = False
    sentence_pairs: List[SentencePair] = []
    key_expressions: List[KeyExpression] = []
    created_at: str
    updated_at: str

class DiaryListItem(BaseModel):
    id: str
    date: str
    title: str
    word_count: int
    grammar_score: int
    is_draft: bool
    is_completed: bool = False
    preview: str
    updated_at: str

class DiaryListResponse(BaseModel):
    diaries: List[DiaryListItem]
    total_count: int
    streak: int
