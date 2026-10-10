import datetime
import json
import logging
import uuid
from typing import List, Optional

import aiosqlite

from app.core.config import settings
from app.schemas.essay import (
    EssayCreateRequest,
    EssayListItem,
    EssayListResponse,
    EssayResponse,
    EssayUpdateRequest,
)
from app.schemas.review import ReviewResponse, SuggestionItem

logger = logging.getLogger(__name__)


def _count_words(text: str) -> int:
    return len(text.split()) if text and text.strip() else 0


def _connect():
    return aiosqlite.connect(settings.DATABASE_PATH)


class EssayService:
    def _row_to_response(self, row: aiosqlite.Row) -> EssayResponse:
        review = None
        if row["review_json"]:
            try:
                review = ReviewResponse(**json.loads(row["review_json"]))
            except Exception as e:
                logger.warning(f"Unreadable review for essay {row['id']}: {e}")
        return EssayResponse(
            id=row["id"],
            date=row["date"],
            topic_id=row["topic_id"],
            prompt=row["prompt"],
            essay_type=row["essay_type"],
            category=row["category"],
            content=row["content"],
            word_count=row["word_count"],
            revision_of=row["revision_of"],
            is_reviewed=review is not None,
            is_completed=bool(row["is_completed"]),
            overall_band=row["overall_band"],
            review=review,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def create(self, req: EssayCreateRequest, content: str = "", revision_of: Optional[str] = None) -> EssayResponse:
        now = datetime.datetime.now()
        essay_id = uuid.uuid4().hex[:12]
        category = req.category or ("free" if req.topic_id is None else "general")
        async with _connect() as db:
            await db.execute(
                """INSERT INTO essays (id, date, topic_id, prompt, essay_type, category, content, word_count,
                                       revision_of, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (essay_id, now.strftime("%Y-%m-%d"), req.topic_id, req.prompt.strip(), req.essay_type, category,
                 content, _count_words(content), revision_of, now.isoformat(), now.isoformat()),
            )
            await db.commit()
        return await self.get(essay_id)

    async def get(self, essay_id: str) -> Optional[EssayResponse]:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute("SELECT * FROM essays WHERE id = ?", (essay_id,))).fetchone()
        return self._row_to_response(row) if row else None

    async def update(self, essay_id: str, req: EssayUpdateRequest) -> Optional[EssayResponse]:
        essay = await self.get(essay_id)
        if not essay:
            return None
        content = essay.content if req.content is None else req.content
        prompt = essay.prompt if req.prompt is None else req.prompt.strip()
        async with _connect() as db:
            await db.execute(
                "UPDATE essays SET content = ?, prompt = ?, word_count = ?, updated_at = ? WHERE id = ?",
                (content, prompt, _count_words(content), datetime.datetime.now().isoformat(), essay_id),
            )
            await db.commit()
        return await self.get(essay_id)

    async def revise(self, essay_id: str) -> Optional[EssayResponse]:
        """Start a rewrite of the same prompt, pre-filled with the previous draft."""
        src = await self.get(essay_id)
        if not src:
            return None
        req = EssayCreateRequest(prompt=src.prompt, essay_type=src.essay_type, category=src.category,
                                 topic_id=src.topic_id)
        return await self.create(req, content=src.content, revision_of=src.id)

    async def save_review(self, essay_id: str, content: str, review: ReviewResponse) -> None:
        async with _connect() as db:
            await db.execute(
                """UPDATE essays SET content = ?, word_count = ?, overall_band = ?, review_json = ?, updated_at = ?
                   WHERE id = ?""",
                (content, _count_words(content), review.rubric.overall_band, review.model_dump_json(),
                 datetime.datetime.now().isoformat(), essay_id),
            )
            await db.commit()
        await self.save_suggestions(essay_id, review.suggestions)

    async def toggle_complete(self, essay_id: str) -> Optional[EssayResponse]:
        async with _connect() as db:
            cur = await db.execute(
                "UPDATE essays SET is_completed = 1 - is_completed WHERE id = ?", (essay_id,))
            await db.commit()
            if cur.rowcount == 0:
                return None
        return await self.get(essay_id)

    async def delete(self, essay_id: str) -> bool:
        async with _connect() as db:
            await db.execute("DELETE FROM essay_suggestions WHERE essay_id = ?", (essay_id,))
            cur = await db.execute("DELETE FROM essays WHERE id = ?", (essay_id,))
            await db.commit()
            return cur.rowcount > 0

    async def list(self) -> EssayListResponse:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute("SELECT * FROM essays ORDER BY created_at DESC")).fetchall()
        items = []
        for r in rows:
            preview = (r["content"] or "").strip().replace("\n", " ")
            items.append(EssayListItem(
                id=r["id"],
                date=r["date"],
                prompt=r["prompt"],
                essay_type=r["essay_type"],
                category=r["category"],
                word_count=r["word_count"],
                revision_of=r["revision_of"],
                is_reviewed=bool(r["review_json"]),
                is_completed=bool(r["is_completed"]),
                overall_band=r["overall_band"],
                preview=preview[:80] + ("..." if len(preview) > 80 else ""),
                updated_at=r["updated_at"],
            ))
        written_dates = {i.date for i in items if i.word_count > 0}
        return EssayListResponse(essays=items, total_count=len(items), streak=current_streak(written_dates))

    async def used_topic_ids(self) -> set:
        async with _connect() as db:
            rows = await (await db.execute("SELECT DISTINCT topic_id FROM essays WHERE topic_id IS NOT NULL")).fetchall()
        return {r[0] for r in rows}

    async def last_essay_type(self) -> Optional[str]:
        async with _connect() as db:
            row = await (await db.execute(
                "SELECT essay_type FROM essays ORDER BY created_at DESC LIMIT 1")).fetchone()
        return row[0] if row else None

    async def save_suggestions(self, essay_id: str, suggestions: List[SuggestionItem]) -> None:
        now = datetime.datetime.now().isoformat()
        async with _connect() as db:
            await db.execute("DELETE FROM essay_suggestions WHERE essay_id = ?", (essay_id,))
            for s in suggestions:
                await db.execute(
                    """INSERT INTO essay_suggestions (id, essay_id, original_phrase, suggested_phrase, category,
                           subcategory, tier, explanation, start_idx, end_idx, is_applied, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s.id or uuid.uuid4().hex[:8], essay_id, s.original_phrase, s.suggested_phrase, s.category,
                     s.subcategory, s.tier, s.explanation, s.start_idx, s.end_idx, int(s.is_applied), now),
                )
            await db.commit()

    async def get_suggestions(self, essay_id: str) -> List[SuggestionItem]:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(
                "SELECT * FROM essay_suggestions WHERE essay_id = ? ORDER BY start_idx", (essay_id,))).fetchall()
        return [
            SuggestionItem(
                id=r["id"], original_phrase=r["original_phrase"], suggested_phrase=r["suggested_phrase"],
                category=r["category"], subcategory=r["subcategory"], tier=r["tier"],
                explanation=r["explanation"], start_idx=r["start_idx"], end_idx=r["end_idx"],
                is_applied=bool(r["is_applied"]),
            )
            for r in rows
        ]


def current_streak(dates: set, today: Optional[datetime.date] = None) -> int:
    """Consecutive writing days ending today (or yesterday, so the streak survives until tonight)."""
    today = today or datetime.date.today()
    day = today if today.isoformat() in dates else today - datetime.timedelta(days=1)
    streak = 0
    while day.isoformat() in dates:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


essay_service = EssayService()
