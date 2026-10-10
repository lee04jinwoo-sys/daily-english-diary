import aiosqlite
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# The old `diaries` / `suggestions` / `anki_history` tables may still exist in older
# databases. They are left untouched; the app no longer reads or writes them.


async def init_db() -> None:
    logger.info(f"Initializing database at {settings.DATABASE_PATH}")
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS essays (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            topic_id TEXT,
            prompt TEXT NOT NULL,
            essay_type TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0,
            revision_of TEXT,
            is_completed INTEGER NOT NULL DEFAULT 0,
            overall_band REAL,
            review_json TEXT,
            writing_seconds INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        cursor = await db.execute("PRAGMA table_info(essays)")
        essay_columns = [row[1] for row in await cursor.fetchall()]
        if "writing_seconds" not in essay_columns:
            await db.execute("ALTER TABLE essays ADD COLUMN writing_seconds INTEGER NOT NULL DEFAULT 0")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS essay_suggestions (
            id TEXT NOT NULL,
            essay_id TEXT NOT NULL,
            original_phrase TEXT NOT NULL,
            suggested_phrase TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'accuracy',
            explanation TEXT NOT NULL,
            start_idx INTEGER NOT NULL,
            end_idx INTEGER NOT NULL,
            is_applied INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            PRIMARY KEY (essay_id, id)
        )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_essays_date ON essays(date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_essay_suggestions_essay ON essay_suggestions(essay_id)")
        await db.commit()
    logger.info("Database schema initialized.")
