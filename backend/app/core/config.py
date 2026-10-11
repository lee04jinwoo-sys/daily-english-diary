import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "essay.db"
LEGACY_DB_NAME = "diary.db"  # name used while this was a diary app


def resolve_db_path(data_dir: Path) -> Path:
    """Return data_dir/essay.db, first renaming a legacy diary.db (and its -wal/-shm) if essay.db is absent.

    Called at startup (init_db), not at import, so importing the app never touches files.
    An existing essay.db always wins and the legacy file is then left alone.
    """
    target = data_dir / "essay.db"
    legacy = data_dir / LEGACY_DB_NAME
    if not target.exists() and legacy.exists():
        for suffix in ("", "-wal", "-shm"):
            src = data_dir / (LEGACY_DB_NAME + suffix)
            if src.exists():
                src.rename(data_dir / ("essay.db" + suffix))
    return target

class Settings(BaseModel):
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    ANKI_URL: str = Field(default_factory=lambda: os.getenv("ANKI_URL", "http://localhost:8765"))
    # Anki Manager's central card gateway: all cards are created through it so its rules apply.
    ANKI_GATEWAY_URL: str = Field(default_factory=lambda: os.getenv("ANKI_GATEWAY_URL", "http://127.0.0.1:8001"))
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    DATABASE_PATH: Path = Field(default_factory=lambda: Path(os.getenv("ESSAY_DB_PATH") or DB_PATH))
    GEMINI_MODEL: str = "gemini-2.5-flash"

settings = Settings()
