import datetime
import difflib
import json
import re
from collections import defaultdict
from typing import Dict, List, Optional

import aiosqlite

from app.core.config import settings
from app.schemas.stats import (
    BandTrendItem, DailyActivity, EssayTrendItem, MistakeSample, StatsResponse, WritingTrendItem,
)
from app.services.essay_service import current_streak


def _avg(xs: List[float], digits: int = 2) -> float:
    return round(sum(xs) / len(xs), digits) if xs else 0.0


# Changes smaller than these are treated as noise when comparing an essay with its baseline.
WPM_NOISE = 0.10          # 10% of the baseline speed
ACCURACY_NOISE = 0.15     # 15% of the baseline must-fix density ...
ACCURACY_NOISE_FLOOR = 0.5  # ... but at least 0.5 per 100 words
BASELINE_ESSAYS = 3
MIN_WRITING_SECONDS = 60


def writing_signal(base_wpm: Optional[float], base_acc: Optional[float], wpm: float, acc: float) -> Optional[str]:
    """How an essay compares with the baseline in speed (wpm) and must-fix errors per 100 words (acc)."""
    if base_wpm is None or base_acc is None:
        return None
    faster = wpm > base_wpm * (1 + WPM_NOISE)
    slower = wpm < base_wpm * (1 - WPM_NOISE)
    band = max(base_acc * ACCURACY_NOISE, ACCURACY_NOISE_FLOOR)
    more_errors = acc > base_acc + band
    fewer_errors = acc < base_acc - band
    if faster:
        return "rushed" if more_errors else "improving"
    if slower:
        return "careful" if fewer_errors else "declining" if more_errors else "slower"
    if fewer_errors:
        return "improving"
    if more_errors:
        return "declining"
    return "steady"


def essay_numbers(essays) -> Dict[str, int]:
    """1, 2, 3 ... for essays with text, in the order they were created."""
    numbers: Dict[str, int] = {}
    for e in essays:
        if (e["word_count"] or 0) > 0:
            numbers[e["id"]] = len(numbers) + 1
    return numbers


def _writing_trends(essays, tier_counts, numbers: Dict[str, int]) -> List[WritingTrendItem]:
    items: List[WritingTrendItem] = []
    baseline: List[WritingTrendItem] = []  # non-revision essays only
    for e in essays:
        words, seconds = e["word_count"] or 0, e["writing_seconds"] or 0
        if not e["review_json"] or words == 0 or seconds < MIN_WRITING_SECONDS:
            continue
        tiers = tier_counts[e["id"]]
        minutes = seconds / 60
        wpm = words / minutes
        acc = tiers.get("accuracy", 0) * 100 / words
        recent = baseline[-BASELINE_ESSAYS:]
        base_wpm = sum(b.wpm for b in recent) / len(recent) if recent else None
        base_acc = sum(b.accuracy_density for b in recent) / len(recent) if recent else None
        item = WritingTrendItem(
            essay_id=e["id"], number=numbers[e["id"]], date=e["date"], essay_type=e["essay_type"],
            is_revision=bool(e["revision_of"]), word_count=words, minutes=round(minutes, 1), wpm=round(wpm, 2),
            error_density=round(sum(tiers.values()) * 100 / words, 2), accuracy_density=round(acc, 2),
            signal=writing_signal(base_wpm, base_acc, wpm, acc),
        )
        items.append(item)
        if not item.is_revision:
            baseline.append(item)
    return items


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+", text) if s.strip()])


class StatsService:
    async def get_stats(self) -> StatsResponse:
        async with aiosqlite.connect(settings.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            essays = await (await db.execute("SELECT * FROM essays ORDER BY created_at")).fetchall()
            sugs = await (await db.execute(
                "SELECT essay_id, category, subcategory, tier, original_phrase, suggested_phrase, explanation "
                "FROM essay_suggestions")).fetchall()

        tier_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        category_counts: Dict[str, int] = defaultdict(int)
        subcats: Dict[str, dict] = {}
        for s in sugs:
            tier_counts[s["essay_id"]][s["tier"]] += 1
            category_counts[s["category"]] += 1
            key = s["subcategory"] or s["category"]
            entry = subcats.setdefault(key, {"category": s["category"], "count": 0, "examples": []})
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append({"original": s["original_phrase"], "suggested": s["suggested_phrase"],
                                          "explanation": s["explanation"]})
        top_subcategories = [
            MistakeSample(category=v["category"], subcategory=k, count=v["count"], examples=v["examples"])
            for k, v in sorted(subcats.items(), key=lambda kv: kv[1]["count"], reverse=True)[:6]
        ]

        # Trends follow writing order: one point per reviewed essay, numbered among essays with text.
        numbers = essay_numbers(essays)
        activity: Dict[str, DailyActivity] = {}
        band_trends: List[BandTrendItem] = []
        essay_trends: List[EssayTrendItem] = []
        type_band_lists: Dict[str, List[float]] = defaultdict(list)
        total_words = total_sentences = 0

        for e in essays:
            date, words = e["date"], e["word_count"] or 0
            if words == 0:
                continue
            act = activity.setdefault(date, DailyActivity(date=date, essay_count=0, word_count=0))
            act.essay_count += 1
            act.word_count += words
            total_words += words

            if not e["review_json"]:
                continue
            review = json.loads(e["review_json"])
            rubric = review["rubric"]
            band = rubric["overall_band"]
            act.best_band = max(band, act.best_band or 0)
            type_band_lists[e["essay_type"]].append(band)
            band_trends.append(BandTrendItem(
                essay_id=e["id"], number=numbers[e["id"]], date=date, essay_type=e["essay_type"],
                revision_of=e["revision_of"], overall_band=band,
                **{k: rubric[k]["band"] for k in ("task_response", "coherence", "lexical", "grammar")},
            ))

            original = review.get("original_text") or e["content"]
            sents = _sentence_count(original)
            total_sentences += sents
            t = tier_counts[e["id"]]
            err = sum(t.values())
            orig_w, corr_w = original.lower().split(), (review.get("corrected_text") or "").lower().split()
            nci = difflib.SequenceMatcher(None, orig_w, corr_w).ratio() * 100 if orig_w and corr_w else 0.0
            essay_trends.append(EssayTrendItem(
                essay_id=e["id"], number=numbers[e["id"]], date=date, essay_type=e["essay_type"],
                word_count=words, sentence_count=sents, error_count=err,
                error_density=round(err / words * 100, 2),
                accuracy_density=round(t.get("accuracy", 0) / words * 100, 2),
                idiom_density=round(t.get("idiom", 0) / words * 100, 2),
                style_density=round(t.get("style", 0) / words * 100, 2),
                nci=round(nci, 1),
            ))

        written = set(activity)
        return StatsResponse(
            total_essays=sum(a.essay_count for a in activity.values()),
            current_streak=current_streak(written),
            max_streak=max_streak(written),
            total_words=total_words,
            total_sentences=total_sentences,
            total_errors=len(sugs),
            avg_error_density=_avg([d.error_density for d in essay_trends]),
            avg_accuracy_density=_avg([d.accuracy_density for d in essay_trends]),
            avg_idiom_density=_avg([d.idiom_density for d in essay_trends]),
            avg_style_density=_avg([d.style_density for d in essay_trends]),
            avg_nci=_avg([d.nci for d in essay_trends], 1),
            avg_band=_avg([b.overall_band for b in band_trends]) if band_trends else None,
            category_counts=dict(category_counts),
            top_subcategories=top_subcategories,
            daily_activity=activity,
            essay_trends=essay_trends,
            band_trends=band_trends,
            type_bands={k: _avg(v) for k, v in type_band_lists.items()},
            writing_trends=_writing_trends(essays, tier_counts, numbers),
        )


def max_streak(dates: set) -> int:
    days = sorted(datetime.date.fromisoformat(d) for d in dates)
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and d - prev == datetime.timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


stats_service = StatsService()
