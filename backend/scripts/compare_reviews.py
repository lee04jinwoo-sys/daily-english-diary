"""Re-review saved essays with the current pipeline and compare with the stored review.

Read-only: the database is opened read-only and nothing is saved back.
Calls Gemini (3 calls per essay). Output: a summary on stdout and full JSON in data/eval/.

    cd backend && .venv/bin/python scripts/compare_reviews.py [essay_id_prefix ...]
"""
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import DATA_DIR, settings  # noqa: E402
from app.services.gemini_service import gemini_service  # noqa: E402

OUT_DIR = DATA_DIR / "eval"


def load_essays(prefixes):
    con = sqlite3.connect(f"file:{settings.DATABASE_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, prompt, essay_type, content, review_json from essays "
        "where review_json is not null order by created_at").fetchall()
    con.close()
    return [r for r in rows if not prefixes or any(r["id"].startswith(p) for p in prefixes)]


def bands(review):
    r = review["rubric"]
    return [r[k]["band"] for k in ("task_response", "coherence", "lexical", "grammar")] + [r["overall_band"]]


def tiers(review):
    out = {"accuracy": 0, "idiom": 0, "style": 0}
    for s in review["suggestions"]:
        out[s["tier"]] = out.get(s["tier"], 0) + 1
    return out


async def main(prefixes):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    settings.REVIEW_METRICS_PATH = OUT_DIR / f"metrics-{stamp}.jsonl"

    # Capture what the verifier saw and rejected (not part of the saved review).
    captured = {}
    original_verify = gemini_service._verify

    async def capturing_verify(essay_id, prompt_text, content, spans, candidates):
        kept, patterns, verified = await original_verify(essay_id, prompt_text, content, spans, candidates)
        kept_ids = {c.id for c in kept}
        captured[essay_id] = {
            "verified": verified,
            "rejected": [{"original": c.original_phrase, "suggested": c.suggested_phrase, "tier": c.tier,
                          "explanation": c.explanation} for c in candidates if c.id not in kept_ids],
        }
        return kept, patterns, verified

    gemini_service._verify = capturing_verify

    results = []
    for row in load_essays(prefixes):
        before = json.loads(row["review_json"])
        after = (await gemini_service.review_essay(row["id"], row["prompt"], row["essay_type"], row["content"])).model_dump()
        results.append({"id": row["id"], "before": before, "after": after, **captured.get(row["id"], {})})

        print(f"\n=== {row['id'][:8]} ({row['essay_type']}) ===")
        print(f"bands  before {bands(before)}  after {bands(after)}")
        print(f"tiers  before {tiers(before)}  after {tiers(after)}")
        print(f"rejected by verifier: {len(captured.get(row['id'], {}).get('rejected', []))}"
              f"  verified={captured.get(row['id'], {}).get('verified')}")
        for r in captured.get(row["id"], {}).get("rejected", []):
            print(f"   - REJECTED [{r['tier']}] {r['original']!r} -> {r['suggested']!r}")
        print("patterns before:")
        for p in before.get("recurring_patterns", []):
            print(f"   - {p['pattern']} x{p['count']} {p['examples']}")
        print("patterns after:")
        for p in after["recurring_patterns"]:
            print(f"   - {p['pattern']} x{p['count']} {p['examples']}")

    out = OUT_DIR / f"compare-{stamp}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nfull results: {out}")
    print(f"call metrics: {settings.REVIEW_METRICS_PATH}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
