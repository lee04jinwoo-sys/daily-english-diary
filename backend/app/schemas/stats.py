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


class EssayTrendItem(BaseModel):
    """One reviewed essay; number is its place in writing order among essays with text."""
    essay_id: str
    number: int
    date: str
    essay_type: str
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
    number: int
    date: str
    essay_type: str
    revision_of: Optional[str] = None
    overall_band: float
    task_response: float
    coherence: float
    lexical: float
    grammar: float


class WritingTrendItem(BaseModel):
    """Speed next to accuracy for one reviewed essay with a recorded writing time."""
    essay_id: str
    number: int
    date: str
    essay_type: str
    is_revision: bool = False
    word_count: int
    minutes: float = Field(..., description="Active writing time (the timer pauses after 2 idle minutes)")
    wpm: float = Field(..., description="Words per active minute")
    error_density: float = Field(..., description="All corrections per 100 words")
    accuracy_density: float = Field(..., description="Must-fix corrections per 100 words")
    signal: Optional[str] = Field(default=None, description=(
        "Compared with the previous up to 3 non-revision essays: "
        "improving | rushed | careful | declining | slower | steady (None without a baseline)"))


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
    essay_trends: List[EssayTrendItem] = Field(default_factory=list, description="Per reviewed essay, in writing order")
    band_trends: List[BandTrendItem] = Field(default_factory=list)
    type_bands: Dict[str, float] = Field(default_factory=dict, description="Average overall band per essay type")
    writing_trends: List[WritingTrendItem] = Field(default_factory=list)
