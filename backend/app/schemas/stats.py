from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MistakeSample(BaseModel):
    category: str
    subcategory: str
    count: int
    examples: List[dict]

class DailyActivity(BaseModel):
    date: str
    has_diary: bool
    word_count: int
    score: int
    is_draft: bool

class DailyTrendItem(BaseModel):
    date: str
    word_count: int
    sentence_count: int
    error_count: int
    error_density: float = Field(default=0.0, description="Total errors per 100 words")
    accuracy_density: float = Field(default=0.0, description="Grammar/accuracy errors per 100 words")
    idiom_density: float = Field(default=0.0, description="Idiom/collocation improvements per 100 words")
    style_density: float = Field(default=0.0, description="Style suggestions per 100 words")
    nci: float = Field(default=85.0, description="Native Conformance Index (%)")

class StatsResponse(BaseModel):
    total_diaries: int
    current_streak: int
    max_streak: int
    total_words: int
    total_sentences: int = Field(default=0)
    total_errors: int = Field(default=0)
    avg_error_density: float = Field(default=0.0, description="Average total errors per 100 words")
    avg_accuracy_density: float = Field(default=0.0, description="Average grammar/accuracy errors per 100 words")
    avg_idiom_density: float = Field(default=0.0, description="Average idiom improvements per 100 words")
    avg_style_density: float = Field(default=0.0, description="Average style suggestions per 100 words")
    avg_nci: float = Field(default=85.0, description="Average Native Conformance Index (%)")
    category_counts: Dict[str, int] = Field(default_factory=dict)
    top_subcategories: List[MistakeSample] = Field(default_factory=list)
    daily_activity: Dict[str, DailyActivity] = Field(default_factory=dict)
    daily_trends: List[DailyTrendItem] = Field(default_factory=list)
