import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Optional

TOPICS_PATH = Path(__file__).resolve().parent.parent / "data" / "topics.json"

# Each type trains different structures: concession/rebuttal, balanced summary,
# weighing, cause-effect, conditionals. "free" is the user's own topic.
ESSAY_TYPES = ["agree_disagree", "discuss_both", "adv_disadv", "problem_solution", "hypothetical", "free"]
CATEGORIES = ["general", "domain", "issues"]
CATEGORY_WEIGHTS = {"general": 0.5, "domain": 0.3, "issues": 0.2}


@lru_cache(maxsize=1)
def _load_topics_cached() -> tuple:
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


def load_topics() -> list[dict]:
    return list(_load_topics_cached())


def pick_topic(
    topics: list[dict],
    used_ids: set,
    exclude_ids: set,
    last_type: Optional[str],
    rng: random.Random,
) -> Optional[dict]:
    """Pick an unwritten topic: category by weight, avoiding the last essay's type when possible.

    When every topic has been written, the bank recycles instead of running dry.
    """
    pool = [t for t in topics if t["id"] not in used_ids and t["id"] not in exclude_ids]
    if not pool:
        pool = [t for t in topics if t["id"] not in exclude_ids] or list(topics)
    if not pool:
        return None

    if last_type:
        fresh_type = [t for t in pool if t["type"] != last_type]
        if fresh_type:
            pool = fresh_type

    by_cat: dict[str, list[dict]] = {}
    for t in pool:
        by_cat.setdefault(t["category"], []).append(t)
    cats = list(by_cat)
    weights = [CATEGORY_WEIGHTS.get(c, 0.1) for c in cats]
    cat = rng.choices(cats, weights=weights, k=1)[0]
    return rng.choice(by_cat[cat])
