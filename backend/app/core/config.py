import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "diary.db"

class Settings(BaseModel):
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    ANKI_URL: str = Field(default_factory=lambda: os.getenv("ANKI_URL", "http://localhost:8765"))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    DATABASE_PATH: Path = Field(default_factory=lambda: Path(os.getenv("ESSAY_DB_PATH") or DB_PATH))
    GEMINI_MODEL: str = "gemini-2.5-flash"
    DEFAULT_ANKI_SENTENCE_DECK: str = Field(default_factory=lambda: os.getenv("DEFAULT_ANKI_SENTENCE_DECK", "Daily_English::Sentences"))
    DEFAULT_ANKI_VOCAB_DECK: str = Field(default_factory=lambda: os.getenv("DEFAULT_ANKI_VOCAB_DECK", "Daily_English::Vocabulary"))

settings = Settings()
