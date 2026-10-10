from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MistakeSample(BaseModel):
    category: str
    subcategory: str
    count: int
    examples: List[dict]


class DailyActivity(BaseModel):
    date: str
    essay_count: int
    word_count: int
    best_band: Optional[float] = None


class DailyTrendItem(BaseModel):
    date: str
    word_count: int
    sentence_count: int
    error_count: int
    error_density: float = Field(default=0.0, description="Total suggestions per 100 words")
    accuracy_density: float = Field(default=0.0, description="Must-fix errors per 100 words")
    idiom_density: float = Field(default=0.0, description="Naturalness fixes per 100 words")
    style_density: float = Field(default=0.0, description="Style suggestions per 100 words")
    nci: float = Field(default=0.0, description="Share of words kept unchanged by the minimal correction (%)")


class BandTrendItem(BaseModel):
    essay_id: str
    date: str
    essay_type: str
    revision_of: Optional[str] = None
    overall_band: float
    task_response: float
    coherence: float
    lexical: float
    grammar: float


class StatsResponse(BaseModel):
    total_essays: int
    current_streak: int
    max_streak: int
    total_words: int
    total_sentences: int = 0
    total_errors: int = 0
    avg_error_density: float = 0.0
    avg_accuracy_density: float = 0.0
    avg_idiom_density: float = 0.0
    avg_style_density: float = 0.0
    avg_nci: float = 0.0
    avg_band: Optional[float] = None
    category_counts: Dict[str, int] = Field(default_factory=dict)
    top_subcategories: List[MistakeSample] = Field(default_factory=list)
    daily_activity: Dict[str, DailyActivity] = Field(default_factory=dict)
    daily_trends: List[DailyTrendItem] = Field(default_factory=list)
    band_trends: List[BandTrendItem] = Field(default_factory=list)
    type_bands: Dict[str, float] = Field(default_factory=dict, description="Average overall band per essay type")
