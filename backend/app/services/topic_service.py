import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Optional

# IELTS Task 2 questions from the btnotpt/ielts_task_2 dataset (Apache-2.0), cleaned by
# scripts/build_ielts_topics.py. `essays` is how many test takers in the dataset wrote on it.
TOPICS_PATH = Path(__file__).resolve().parent.parent / "data" / "ielts_topics.json"

# Each type trains different structures: concession/rebuttal, balanced summary, weighing,
# cause-effect, answering two questions. "hypothetical" and the old categories only remain
# on essays written from the earlier hand-made bank; "free" is the user's own topic.
ESSAY_TYPES = ["agree_disagree", "discuss_both", "adv_disadv", "problem_solution", "two_part", "hypothetical", "free"]
BANK_TYPES = ["agree_disagree", "discuss_both", "adv_disadv", "problem_solution", "two_part"]
THEMES = ["education", "technology", "work", "environment", "health", "society", "government",
          "crime", "culture", "family", "media", "transport", "economy", "science", "travel", "sport"]


@lru_cache(maxsize=1)
def _load_topics_cached() -> tuple:
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


def load_topics() -> list[dict]:
    return list(_load_topics_cached())


def theme_of(topic_id: Optional[str]) -> Optional[str]:
    if not topic_id:
        return None
    return next((t["theme"] for t in _load_topics_cached() if t["id"] == topic_id), None)


def pick_topic(
    topics: list[dict],
    used_ids: set,
    exclude_ids: set,
    last_type: Optional[str],
    rng: random.Random,
    last_theme: Optional[str] = None,
) -> Optional[dict]:
    """Pick an unwritten topic: a type chosen evenly, not the last essay's type or theme when possible.

    Types are drawn evenly because the source bank is mostly agree/disagree questions.
    When every topic has been written, the bank recycles instead of running dry.
    """
    pool = [t for t in topics if t["id"] not in used_ids and t["id"] not in exclude_ids]
    if not pool:
        pool = [t for t in topics if t["id"] not in exclude_ids] or list(topics)
    if not pool:
        return None

    for key, last in (("type", last_type), ("theme", last_theme)):
        if last:
            fresh = [t for t in pool if t.get(key) != last]
            if fresh:
                pool = fresh

    by_type: dict[str, list[dict]] = {}
    for t in pool:
        by_type.setdefault(t["type"], []).append(t)
    type_ = rng.choice(sorted(by_type))
    return rng.choice(by_type[type_])
