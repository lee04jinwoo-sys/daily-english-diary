import uuid
import datetime
import json
import logging
from typing import Optional, List, Dict, Any
import aiosqlite
from app.core.config import settings
from app.schemas.diary import DiarySaveRequest, DiaryResponse, DiaryListItem, DiaryListResponse
from app.schemas.review import SuggestionItem, SentencePair, KeyExpression

logger = logging.getLogger(__name__)

class DiaryService:
    @staticmethod
    def _count_words(text: str) -> int:
        if not text:
            return 0
        return len(text.strip().split())

    async def get_diary_by_date(self, date: str) -> Optional[DiaryResponse]:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM diaries WHERE date = ?", (date,))
            row = await cursor.fetchone()
            if not row:
                return None
            
            # Parse sentence_pairs & key_expressions JSON
            sentence_pairs = []
            try:
                raw_sp = row["sentence_pairs"] if "sentence_pairs" in row.keys() else "[]"
                if raw_sp:
                    parsed_sp = json.loads(raw_sp)
                    sentence_pairs = [SentencePair(**item) for item in parsed_sp]
            except Exception as e:
                logger.warning(f"Error parsing sentence_pairs: {e}")

            key_exprs = []
            try:
                raw_ke = row["key_expressions"] if "key_expressions" in row.keys() else "[]"
                if raw_ke:
                    parsed_ke = json.loads(raw_ke)
                    key_exprs = [KeyExpression(**item) for item in parsed_ke]
            except Exception as e:
                logger.warning(f"Error parsing key_expressions: {e}")

            return DiaryResponse(
                id=row["id"],
                date=row["date"],
                title=row["title"],
                content=row["content"],
                corrected_content=row["corrected_content"] or "",
                native_content=row["native_content"] or "",
                overall_feedback=row["overall_feedback"] or "",
                grammar_score=row["grammar_score"] or 100,
                word_count=row["word_count"] or 0,
                is_draft=bool(row["is_draft"]),
                is_completed=bool(row["is_completed"]) if "is_completed" in row.keys() else False,
                sentence_pairs=sentence_pairs,
                key_expressions=key_exprs,
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    async def save_diary(self, req: DiarySaveRequest) -> DiaryResponse:
        now_iso = datetime.datetime.now().isoformat()
        word_cnt = self._count_words(req.content)

        sp_json = json.dumps([sp.model_dump() for sp in (req.sentence_pairs or [])], ensure_ascii=False)
        ke_json = json.dumps([ke.model_dump() for ke in (req.key_expressions or [])], ensure_ascii=False)

        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT id, created_at, sentence_pairs, key_expressions, is_completed FROM diaries WHERE date = ?", (req.date,))
            existing = await cursor.fetchone()

            if existing:
                diary_id = existing["id"]
                created_at = existing["created_at"]
                
                final_sp_json = sp_json if (req.sentence_pairs and len(req.sentence_pairs) > 0) else (existing["sentence_pairs"] or "[]")
                final_ke_json = ke_json if (req.key_expressions and len(req.key_expressions) > 0) else (existing["key_expressions"] or "[]")
                comp_val = 1 if req.is_completed else (existing["is_completed"] or 0)

                await db.execute("""
                UPDATE diaries
                SET title = ?, content = ?, corrected_content = ?, native_content = ?,
                    overall_feedback = ?, grammar_score = ?, word_count = ?, is_draft = ?,
                    is_completed = ?, sentence_pairs = ?, key_expressions = ?, updated_at = ?
                WHERE date = ?
                """, (
                    req.title, req.content, req.corrected_content or "", req.native_content or "",
                    req.overall_feedback or "", req.grammar_score or 100, word_cnt,
                    1 if req.is_draft else 0, comp_val, final_sp_json, final_ke_json, now_iso, req.date
                ))
            else:
                diary_id = str(uuid.uuid4())
                created_at = now_iso
                comp_val = 1 if req.is_completed else 0
                await db.execute("""
                INSERT INTO diaries (
                    id, date, title, content, corrected_content, native_content,
                    overall_feedback, grammar_score, word_count, is_draft, is_completed,
                    sentence_pairs, key_expressions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    diary_id, req.date, req.title, req.content, req.corrected_content or "",
                    req.native_content or "", req.overall_feedback or "", req.grammar_score or 100,
                    word_cnt, 1 if req.is_draft else 0, comp_val, sp_json, ke_json, created_at, now_iso
                ))

            await db.commit()

        return DiaryResponse(
            id=diary_id,
            date=req.date,
            title=req.title,
            content=req.content,
            corrected_content=req.corrected_content or "",
            native_content=req.native_content or "",
            overall_feedback=req.overall_feedback or "",
            grammar_score=req.grammar_score or 100,
            word_count=word_cnt,
            is_draft=req.is_draft,
            is_completed=bool(comp_val),
            sentence_pairs=req.sentence_pairs or [],
            key_expressions=req.key_expressions or [],
            created_at=created_at,
            updated_at=now_iso
        )

    async def toggle_complete(self, date: str) -> Optional[DiaryResponse]:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT is_completed FROM diaries WHERE date = ?", (date,))
            row = await cursor.fetchone()
            if not row:
                return None
            curr_val = bool(row["is_completed"]) if "is_completed" in row.keys() else False
            new_val = 0 if curr_val else 1
            await db.execute("UPDATE diaries SET is_completed = ? WHERE date = ?", (new_val, date))
            await db.commit()
        return await self.get_diary_by_date(date)

    async def list_diaries(self) -> DiaryListResponse:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM diaries ORDER BY date DESC")
            rows = await cursor.fetchall()

            items = []
            dates_written = set()
            for r in rows:
                if not r["is_draft"] and r["content"]:
                    dates_written.add(r["date"])
                
                preview_text = (r["content"] or "").strip().replace("\n", " ")
                if len(preview_text) > 80:
                    preview_text = preview_text[:80] + "..."

                items.append(DiaryListItem(
                    id=r["id"],
                    date=r["date"],
                    title=r["title"] or "제목 없음",
                    word_count=r["word_count"] or 0,
                    grammar_score=r["grammar_score"] or 100,
                    is_draft=bool(r["is_draft"]),
                    is_completed=bool(r["is_completed"]) if "is_completed" in r.keys() else False,
                    preview=preview_text,
                    updated_at=r["updated_at"]
                ))

            streak = self._calculate_streak(dates_written)

            return DiaryListResponse(
                diaries=items,
                total_count=len(items),
                streak=streak
            )

    def _calculate_streak(self, dates_set: set) -> int:
        if not dates_set:
            return 0
        
        today = datetime.date.today()
        current = today
        streak = 0
        
        today_str = today.strftime("%Y-%m-%d")
        if today_str in dates_set:
            streak += 1
            current -= datetime.timedelta(days=1)
        else:
            yesterday_str = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            if yesterday_str in dates_set:
                current = today - datetime.timedelta(days=1)
            else:
                return 0

        while True:
            d_str = current.strftime("%Y-%m-%d")
            if d_str in dates_set:
                streak += 1
                current -= datetime.timedelta(days=1)
            else:
                break
        return streak

    async def save_suggestions(self, diary_date: str, suggestions: List[SuggestionItem]) -> None:
        now_iso = datetime.datetime.now().isoformat()
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            await db.execute("DELETE FROM suggestions WHERE diary_date = ?", (diary_date,))
            for s in suggestions:
                s_id = s.id or str(uuid.uuid4())[:8]
                s_tier = getattr(s, "tier", "accuracy") or "accuracy"
                await db.execute("""
                INSERT INTO suggestions (
                    id, diary_date, original_phrase, suggested_phrase, category,
                    subcategory, tier, explanation, start_idx, end_idx, is_applied, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s_id, diary_date, s.original_phrase, s.suggested_phrase,
                    f"{s.category}:{s.subcategory}", s.subcategory, s_tier,
                    s.explanation, s.start_idx, s.end_idx,
                    1 if s.is_applied else 0, now_iso
                ))
            await db.commit()

    async def get_suggestions(self, diary_date: str) -> List[SuggestionItem]:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM suggestions WHERE diary_date = ? ORDER BY start_idx ASC", (diary_date,))
            rows = await cursor.fetchall()
            
            res = []
            for r in rows:
                raw_cat = r["category"]
                cat_parts = raw_cat.split(":", 1)
                main_cat = cat_parts[0]
                sub_cat = cat_parts[1] if len(cat_parts) > 1 else ""
                
                is_app = bool(r["is_applied"]) if "is_applied" in r.keys() else False
                r_tier = r["tier"] if "tier" in r.keys() and r["tier"] else "accuracy"

                res.append(SuggestionItem(
                    id=r["id"],
                    original_phrase=r["original_phrase"],
                    suggested_phrase=r["suggested_phrase"],
                    category=main_cat,
                    subcategory=sub_cat,
                    tier=r_tier,
                    explanation=r["explanation"],
                    start_idx=r["start_idx"],
                    end_idx=r["end_idx"],
                    is_applied=is_app
                ))
            return res

    async def delete_diary(self, date: str) -> bool:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            await db.execute("DELETE FROM suggestions WHERE diary_date = ?", (date,))
            cursor = await db.execute("DELETE FROM diaries WHERE date = ?", (date,))
            await db.commit()
            return cursor.rowcount > 0

diary_service = DiaryService()
