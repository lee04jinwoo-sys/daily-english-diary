import aiosqlite
import logging
from typing import AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db

async def init_db() -> None:
    logger.info(f"Initializing database at {settings.DATABASE_PATH}")
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        
        # Diaries table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS diaries (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            corrected_content TEXT DEFAULT '',
            native_content TEXT DEFAULT '',
            overall_feedback TEXT DEFAULT '',
            grammar_score INTEGER DEFAULT 100,
            word_count INTEGER DEFAULT 0,
            is_draft INTEGER DEFAULT 1,
            sentence_pairs TEXT DEFAULT '[]',
            key_expressions TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Check if columns exist in existing database (migration)
        cursor = await db.execute("PRAGMA table_info(diaries)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "sentence_pairs" not in columns:
            await db.execute("ALTER TABLE diaries ADD COLUMN sentence_pairs TEXT DEFAULT '[]'")
        if "key_expressions" not in columns:
            await db.execute("ALTER TABLE diaries ADD COLUMN key_expressions TEXT DEFAULT '[]'")
        if "is_completed" not in columns:
            await db.execute("ALTER TABLE diaries ADD COLUMN is_completed INTEGER DEFAULT 0")

        # Suggestions table (Grammarly items)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id TEXT PRIMARY KEY,
            diary_date TEXT NOT NULL,
            original_phrase TEXT NOT NULL,
            suggested_phrase TEXT NOT NULL,
            category TEXT NOT NULL,
            explanation TEXT NOT NULL,
            start_idx INTEGER NOT NULL,
            end_idx INTEGER NOT NULL,
            is_applied INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (diary_date) REFERENCES diaries (date) ON DELETE CASCADE
        )
        """)

        # Anki cards history
        await db.execute("""
        CREATE TABLE IF NOT EXISTS anki_history (
            id TEXT PRIMARY KEY,
            diary_date TEXT NOT NULL,
            card_type TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            deck_name TEXT NOT NULL,
            note_id INTEGER,
            created_at TEXT NOT NULL
        )
        """)
        
        # Index for fast date lookups
        await db.execute("CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_date ON suggestions(diary_date)")
        
        await db.commit()
    logger.info("Database schema initialized successfully with sentence_pairs support.")
