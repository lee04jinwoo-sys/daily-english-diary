"""Build app/data/ielts_topics.json from the btnotpt/ielts_task_2 dataset (Apache-2.0).

    curl -L -o /tmp/ielts/train.parquet https://huggingface.co/datasets/btnotpt/ielts_task_2/resolve/main/data/train-00000-of-00001.parquet
    curl -L -o /tmp/ielts/test.parquet  https://huggingface.co/datasets/btnotpt/ielts_task_2/resolve/main/data/test-00000-of-00001.parquet
    .venv/bin/pip install pyarrow   # only this script needs it
    .venv/bin/python scripts/build_ielts_topics.py /tmp/ielts/train.parquet /tmp/ielts/test.parquet [--dry-run]

Steps: deterministic cleanup (app/services/ielts_bank.py), then Gemini checks each question
is a real Task 2 question, classifies it, and fixes spelling/grammar only. A fix that changes
more than MAX_FIX_CHANGE of the text is treated as a rewrite and the question is dropped.
"""
import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ielts_bank import accept_fix, clean_prompt, dedupe_variants, is_candidate  # noqa: E402
from app.services.topic_service import BANK_TYPES as TYPES, THEMES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "ielts_topics.json"
BATCH = 40


def load_counts(paths) -> Counter:
    import pyarrow.parquet as pq
    counts: Counter = Counter()
    for p in paths:
        for row in pq.read_table(p, columns=["topic"]).to_pylist():
            if row["topic"]:
                counts[clean_prompt(row["topic"])] += 1
    return counts


PROMPT = """You are cleaning a bank of IELTS Academic Writing Task 2 questions typed in by test takers.
For each item return an object with:
- "i": the item index, unchanged
- "keep": true only if this is a complete, sensible IELTS Task 2 essay question
- "type": one of {types}
    agree_disagree = to what extent do you agree / do you agree; also "is this a positive or negative development"
    discuss_both = discuss both views and give your opinion
    adv_disadv = advantages and disadvantages / do the advantages outweigh
    problem_solution = causes / problems with solutions or effects
    two_part = two or more direct questions that do not fit the types above
- "theme": one of {themes}
- "text": the question with spelling, grammar, capitalisation and punctuation corrected.
  Keep the original wording and meaning; change as little as possible. Do not add or remove sentences.
Return JSON: {{"items": [...]}}

Items:
{items}"""


async def review_batch(client, model, batch):
    from google.genai import types
    items = "\n".join(json.dumps({"i": i, "text": t}) for i, t in batch)
    prompt = PROMPT.format(types=TYPES, themes=THEMES, items=items)
    for attempt in range(3):
        try:
            res = await client.aio.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            return json.loads(res.text)["items"]
        except Exception as e:  # bad JSON or a transient API error
            print(f"batch {batch[0][0]} attempt {attempt + 1} failed: {e}", file=sys.stderr)
            await asyncio.sleep(2 * (attempt + 1))
    return []


async def gemini_pass(texts):
    from google import genai
    from app.core.config import settings
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    sem = asyncio.Semaphore(8)
    indexed = list(enumerate(texts))
    batches = [indexed[k:k + BATCH] for k in range(0, len(indexed), BATCH)]

    async def run(b):
        async with sem:
            return await review_batch(client, settings.GEMINI_MODEL, b)

    results = await asyncio.gather(*(run(b) for b in batches))
    return {r["i"]: r for batch in results for r in batch if isinstance(r, dict) and "i" in r}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet", nargs="+")
    ap.add_argument("--dry-run", action="store_true", help="deterministic steps only, no Gemini, no output file")
    args = ap.parse_args()

    counts = load_counts(args.parquet)
    candidates = {t: n for t, n in counts.items() if is_candidate(t)}
    merged = dedupe_variants(candidates)
    print(f"distinct {len(counts)} -> candidates {len(candidates)} -> after merging variants {len(merged)}")
    if args.dry_run:
        return

    texts = list(merged)
    reviewed = asyncio.run(gemini_pass(texts))
    stats = Counter()
    bank = []
    for i, text in enumerate(texts):
        r = reviewed.get(i)
        if not r:
            stats["no_answer"] += 1
            continue
        if not r.get("keep"):
            stats["not_task2"] += 1
            continue
        fixed = accept_fix(text, r.get("text", ""))
        if fixed is None:
            stats["rewritten"] += 1
            continue
        if r.get("type") not in TYPES or r.get("theme") not in THEMES:
            stats["bad_label"] += 1
            continue
        stats["kept"] += 1
        stats["changed"] += fixed != text
        bank.append({"type": r["type"], "theme": r["theme"], "prompt": fixed, "essays": merged[text]})

    bank.sort(key=lambda t: (-t["essays"], t["prompt"]))
    for n, t in enumerate(bank, 1):
        t["id"] = f"ielts-{n:04d}"
        t["category"] = "ielts"
    bank = [{k: t[k] for k in ("id", "category", "type", "theme", "prompt", "essays")} for t in bank]
    OUT.write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(dict(stats))
    print("types", Counter(t["type"] for t in bank))
    print("themes", Counter(t["theme"] for t in bank))
    print(f"wrote {len(bank)} topics to {OUT}")


if __name__ == "__main__":
    main()
