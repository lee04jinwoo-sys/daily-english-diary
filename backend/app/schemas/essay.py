from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.review import ReviewResponse

EssayType = Literal["agree_disagree", "discuss_both", "adv_disadv", "problem_solution", "hypothetical", "free"]
EssayCategory = Literal["general", "domain", "issues", "free"]


class EssayCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="Essay question (from the bank or the user's own)")
    essay_type: EssayType = "free"
    category: Optional[EssayCategory] = None
    topic_id: Optional[str] = Field(default=None, description="Topic bank id; None for a free topic")


class EssayUpdateRequest(BaseModel):
    content: Optional[str] = None
    prompt: Optional[str] = None
    writing_seconds: Optional[int] = Field(default=None, ge=0, description="Active writing time; never decreases")


class EssayResponse(BaseModel):
    id: str
    date: str
    topic_id: Optional[str] = None
    prompt: str
    essay_type: EssayType
    category: EssayCategory
    content: str = ""
    word_count: int = 0
    revision_of: Optional[str] = None
    is_reviewed: bool = False
    is_completed: bool = False
    overall_band: Optional[float] = None
    writing_seconds: int = 0
    review: Optional[ReviewResponse] = None
    created_at: str
    updated_at: str


class EssayListItem(BaseModel):
    id: str
    date: str
    prompt: str
    essay_type: EssayType
    category: EssayCategory
    word_count: int
    revision_of: Optional[str] = None
    is_reviewed: bool
    is_completed: bool
    overall_band: Optional[float] = None
    writing_seconds: int = 0
    preview: str
    updated_at: str


class EssayListResponse(BaseModel):
    essays: List[EssayListItem]
    total_count: int
    streak: int


class TopicResponse(BaseModel):
    id: str
    category: EssayCategory
    type: EssayType
    prompt: str
