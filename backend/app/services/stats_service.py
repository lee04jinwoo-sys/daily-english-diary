import datetime
import difflib
import json
import logging
import re
from collections import defaultdict
from typing import Dict, List, Any
import aiosqlite
from app.core.config import settings
from app.schemas.stats import (
    StatsResponse,
    MistakeSample,
    DailyActivity,
    DailyTrendItem
)

logger = logging.getLogger(__name__)


class StatsService:
    async def get_stats(self) -> StatsResponse:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row

            # 1. Fetch suggestions count per diary (tier-aware)
            sug_cursor = await db.execute("""
                SELECT diary_date, category, tier, COUNT(*) as cnt 
                FROM suggestions 
                GROUP BY diary_date, category, tier
            """)
            sug_rows = await sug_cursor.fetchall()
            date_error_counts: Dict[str, int] = defaultdict(int)
            date_tier_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            date_cat_errors: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            category_counts: Dict[str, int] = defaultdict(int)

            for row in sug_rows:
                d_date = row["diary_date"]
                raw_cat = row["category"] or ""
                main_cat = raw_cat.split(":")[0].strip()
                tier = row["tier"] if ("tier" in row.keys() and row["tier"]) else "accuracy"
                cnt = row["cnt"]

                date_error_counts[d_date] += cnt
                date_tier_counts[d_date][tier] += cnt
                date_cat_errors[d_date][main_cat] += cnt
                category_counts[main_cat] += cnt

            # 2. Fetch top suggestions samples
            cursor = await db.execute("SELECT category, original_phrase, suggested_phrase, explanation FROM suggestions")
            all_suggestions = await cursor.fetchall()
            subcat_samples: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"category": "", "count": 0, "examples": []})

            for s in all_suggestions:
                raw_cat = s["category"]
                cat_parts = raw_cat.split(":", 1)
                main_cat = cat_parts[0]
                sub_cat = cat_parts[1] if len(cat_parts) > 1 and cat_parts[1] else main_cat

                subcat_samples[sub_cat]["category"] = main_cat
                subcat_samples[sub_cat]["count"] += 1
                if len(subcat_samples[sub_cat]["examples"]) < 3:
                    subcat_samples[sub_cat]["examples"].append({
                        "original": s["original_phrase"],
                        "suggested": s["suggested_phrase"],
                        "explanation": s["explanation"]
                    })

            sorted_subcats = sorted(subcat_samples.items(), key=lambda x: x[1]["count"], reverse=True)
            top_subcategories = [
                MistakeSample(
                    category=data["category"],
                    subcategory=subcat_name,
                    count=data["count"],
                    examples=data["examples"]
                )
                for subcat_name, data in sorted_subcats[:6]
            ]

            # 3. Diaries overview & daily trends
            cursor = await db.execute("""
                SELECT date, title, content, word_count, grammar_score, is_draft, sentence_pairs, corrected_content 
                FROM diaries 
                ORDER BY date ASC
            """)
            diaries = await cursor.fetchall()

            total_diaries = 0
            total_words = 0
            total_sentences = 0
            total_errors = sum(date_error_counts.values())
            dates_written = set()
            daily_activity: Dict[str, DailyActivity] = {}
            daily_trends: List[DailyTrendItem] = []

            error_densities: List[float] = []
            accuracy_densities: List[float] = []
            idiom_densities: List[float] = []
            style_densities: List[float] = []
            ncis: List[float] = []

            for d in diaries:
                d_date = d["date"]
                is_draft = bool(d["is_draft"])
                content = d["content"] or ""
                corr_content = d["corrected_content"] or ""
                w_cnt = d["word_count"] or (len(content.split()) if content.strip() else 0)

                # Count sentences
                s_cnt = 0
                if d["sentence_pairs"]:
                    try:
                        pairs = json.loads(d["sentence_pairs"])
                        s_cnt = len(pairs)
                    except Exception:
                        s_cnt = len(re.split(r'[.!?]+', content.strip())) - 1
                else:
                    s_cnt = max(1, len(re.split(r'[.!?]+', content.strip())) - 1) if content.strip() else 0

                err_cnt = date_error_counts.get(d_date, 0)
                acc_cnt = date_tier_counts[d_date].get("accuracy", 0)
                idiom_cnt = date_tier_counts[d_date].get("idiom", 0)
                style_cnt = date_tier_counts[d_date].get("style", 0)

                # 1. 3-Tier Error Densities (Errors per 100 words)
                acc_density = round((acc_cnt / max(w_cnt, 1)) * 100, 2)
                idiom_density = round((idiom_cnt / max(w_cnt, 1)) * 100, 2)
                style_density = round((style_cnt / max(w_cnt, 1)) * 100, 2)
                err_density = round((err_cnt / max(w_cnt, 1)) * 100, 2)

                # 2. Native Conformance Index (NCI %): ratio of words needing no edits
                orig_words = content.lower().split()
                corr_words = corr_content.lower().split()
                if orig_words and corr_words:
                    matcher = difflib.SequenceMatcher(None, orig_words, corr_words)
                    nci_val = round(matcher.ratio() * 100, 1)
                elif orig_words:
                    nci_val = round(max(50.0, min(100.0, 100.0 - err_density * 3.0)), 1)
                else:
                    nci_val = 85.0

                if not is_draft and w_cnt > 0:
                    total_diaries += 1
                    total_words += w_cnt
                    total_sentences += s_cnt
                    dates_written.add(d_date)
                    error_densities.append(err_density)
                    accuracy_densities.append(acc_density)
                    idiom_densities.append(idiom_density)
                    style_densities.append(style_density)
                    ncis.append(nci_val)

                    daily_trends.append(DailyTrendItem(
                        date=d_date,
                        word_count=w_cnt,
                        sentence_count=s_cnt,
                        error_count=err_cnt,
                        error_density=err_density,
                        accuracy_density=acc_density,
                        idiom_density=idiom_density,
                        style_density=style_density,
                        nci=nci_val
                    ))

                daily_activity[d_date] = DailyActivity(
                    date=d_date,
                    has_diary=(w_cnt > 0),
                    word_count=w_cnt,
                    score=int(round(nci_val)),
                    is_draft=is_draft
                )

            avg_error_density = round(sum(error_densities) / len(error_densities), 2) if error_densities else 0.0
            avg_accuracy_density = round(sum(accuracy_densities) / len(accuracy_densities), 2) if accuracy_densities else 0.0
            avg_idiom_density = round(sum(idiom_densities) / len(idiom_densities), 2) if idiom_densities else 0.0
            avg_style_density = round(sum(style_densities) / len(style_densities), 2) if style_densities else 0.0
            avg_nci = round(sum(ncis) / len(ncis), 1) if ncis else 85.0
            current_streak, max_streak = self._calculate_streaks(dates_written)

            return StatsResponse(
                total_diaries=total_diaries,
                current_streak=current_streak,
                max_streak=max_streak,
                total_words=total_words,
                total_sentences=total_sentences,
                total_errors=total_errors,
                avg_error_density=avg_error_density,
                avg_accuracy_density=avg_accuracy_density,
                avg_idiom_density=avg_idiom_density,
                avg_style_density=avg_style_density,
                avg_nci=avg_nci,
                category_counts=dict(category_counts),
                top_subcategories=top_subcategories,
                daily_activity=daily_activity,
                daily_trends=daily_trends
            )

    def _calculate_streaks(self, dates_set: set) -> tuple[int, int]:
        if not dates_set:
            return 0, 0

        # Sort all dates
        sorted_dates = sorted([datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in dates_set])
        
        # Max streak
        max_streak = 1
        curr_streak_run = 1
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i-1] + datetime.timedelta(days=1):
                curr_streak_run += 1
                if curr_streak_run > max_streak:
                    max_streak = curr_streak_run
            elif sorted_dates[i] > sorted_dates[i-1] + datetime.timedelta(days=1):
                curr_streak_run = 1

        # Current streak from today/yesterday
        today = datetime.date.today()
        current = today
        current_streak = 0
        today_str = today.strftime("%Y-%m-%d")

        if today_str in dates_set:
            current_streak += 1
            current -= datetime.timedelta(days=1)
        else:
            yesterday_str = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            if yesterday_str in dates_set:
                current = today - datetime.timedelta(days=1)
            else:
                return 0, max_streak

        while True:
            d_str = current.strftime("%Y-%m-%d")
            if d_str in dates_set:
                current_streak += 1
                current -= datetime.timedelta(days=1)
            else:
                break

        return current_streak, max(max_streak, current_streak)

stats_service = StatsService()
