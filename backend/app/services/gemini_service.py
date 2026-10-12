import asyncio
import json
import math
import statistics
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.review import (
    ReviewResponse, SuggestionItem, KeyExpression, SentencePair, VocabItem,
    EssayRubric, CriterionScore, ArgumentFeedback, ParagraphComment, RecurringPattern,
)
from app.schemas.anki import CardPreviewResponse, CardType
from app.services.text_utils import apply_suggestions, split_sentences
from app.services.review_prompts import (
    build_main_prompt, build_detect_prompt, build_verify_prompt,
    build_content_score_prompt, build_language_score_prompt,
)

logger = logging.getLogger(__name__)

def normalize_vocab_placeholders(word: str) -> str:
    """Normalize placeholders like someone, something, sb, sth to A, B, C and doing to V-ing."""
    if not word:
        return ""
    # 1. Normalize '~ing', '~-ing', '~ ing', 'doing something', 'doing sth', 'doing' to 'V-ing'
    word = re.sub(r"~\s*-?ing\b", "V-ing", word, flags=re.IGNORECASE)
    word = re.sub(r"~\s*동사원형\b", "V", word, flags=re.IGNORECASE)
    word = re.sub(r"~\s*원형\b", "V", word, flags=re.IGNORECASE)
    word = re.sub(r"\bdoing\s+(something|sth)\b", "V-ing", word, flags=re.IGNORECASE)
    word = re.sub(r"\bdoing\b", "V-ing", word, flags=re.IGNORECASE)
    word = re.sub(r"~\b", "A", word)

    # 2. Normalize 'sb', 'sth', 'someone', 'something', 'somebody', 'sbd' to A, B, C
    pattern = r"\b(someone|somebody|sb|sbd|something|sth)\b"
    placeholders = ["A", "B", "C"]
    placeholder_idx = 0

    def repl(match: re.Match) -> str:
        nonlocal placeholder_idx
        if placeholder_idx < len(placeholders):
            res = placeholders[placeholder_idx]
            placeholder_idx += 1
            return res
        return match.group(0)

    normalized = re.sub(pattern, repl, word, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def clean_vocab_example(example: str) -> str:
    """Removes any Korean translations or bracketed Korean notes from English example sentences."""
    if not example:
        return ""
    # Remove (한글...), [한글...]
    cleaned = re.sub(r"\s*[\(\[][^()\[\]]*[가-힣]+[^()\[\]]*[\)\]]", "", example)
    # Remove - 한글... or : 한글... at end
    cleaned = re.sub(r"\s*[-:]\s*[가-힣\s,.~!?]+$", "", cleaned)
    return cleaned.strip()

ESSAY_TYPE_GUIDE = {
    "agree_disagree": "찬반형 - 분명한 입장, 반대 측 인정 후 반박(양보-반박 구조)이 핵심",
    "discuss_both": "양쪽 견해 논의형 - 두 견해를 공정하게 설명한 뒤 자신의 결론을 분명히",
    "adv_disadv": "장단점형 - 장단점을 비교하고 어느 쪽이 더 큰지 판단과 근거 제시",
    "problem_solution": "원인·해결책형 - 인과관계의 구체성, 해결책의 실행 가능성",
    "hypothetical": "가정형 - 가정법의 정확한 사용, 결과의 논리적 추론",
    "free": "자유 주제 - 학습자가 정한 질문에 대한 논증문",
}


MAX_SUGGESTION_WORDS = 12
REVIEW_THINKING_BUDGET = 2048
DETECT_THINKING_BUDGET = 2048
VERIFY_THINKING_BUDGET = 1024
SCORE_RUNS = 3
SCORE_TEMPERATURE = 0.7  # independent runs, so the median can smooth out one-off swings
SCORE_THINKING_BUDGET = 1024
CRITERIA = ("task_response", "coherence", "lexical", "grammar")
CONTENT_CRITERIA = ("task_response", "coherence")
LANGUAGE_CRITERIA = ("grammar", "lexical")


def record_metric(row: dict) -> None:
    """Append one JSON line to the review metrics file (never fails the review)."""
    path = settings.REVIEW_METRICS_PATH
    if not path:
        return
    try:
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning(f"Could not write review metrics: {e}")


_CONTRACTIONS = [
    (r"\bwon't\b", "will not"), (r"\bcan't\b", "cannot"), (r"\bcan not\b", "cannot"), (r"\bshan't\b", "shall not"),
    (r"n't\b", " not"), (r"'re\b", " are"), (r"'m\b", " am"), (r"'ve\b", " have"), (r"'ll\b", " will"),
]


def _expand(text: str, s_form: str, d_form: str) -> str:
    t = text.lower().replace("\u2019", "'")
    for pat, repl in _CONTRACTIONS:
        t = re.sub(pat, repl, t)
    t = re.sub(r"'s\b", " " + s_form, t)
    t = re.sub(r"'d\b", " " + d_form, t)
    return " ".join(t.split())


def is_contraction_only(original: str, suggested: str) -> bool:
    """True when the suggestion merely expands (or creates) contractions."""
    if not original or not suggested or original.strip() == suggested.strip():
        return False
    for s_form in ("is", "has"):
        for d_form in ("would", "had"):
            if _expand(original, s_form, d_form) == _expand(suggested, s_form, d_form):
                return True
    return False


def parse_patterns(raw) -> list[RecurringPattern]:
    out: list[RecurringPattern] = []
    for p in raw or []:
        if not isinstance(p, dict) or not str(p.get("pattern", "")).strip():
            continue
        examples = p.get("examples") or []
        if isinstance(examples, str):
            examples = [examples]
        try:
            count = int(p.get("count", len(examples)))
        except (TypeError, ValueError):
            count = len(examples)
        out.append(RecurringPattern(
            pattern=str(p["pattern"]).strip(),
            count=max(count, 1),
            examples=[str(x) for x in examples if str(x).strip()],
            fix=str(p.get("fix", "")),
            tip=str(p.get("tip", "")),
        ))
    return out[:4]


def half_band(value: float) -> float:
    """Nearest 0.5, halves rounded up (6.25 -> 6.5), clamped to 0-9."""
    return min(9.0, max(0.0, math.floor(value * 2 + 0.5) / 2))


def ielts_overall(bands) -> float:
    """IELTS overall: mean of the criteria; .25 rounds up to .5 and .75 up to the next band."""
    return half_band(sum(bands) / len(bands))


def parse_score_run(raw, criteria=CRITERIA) -> Optional[dict]:
    """{criterion: (band, comment)} from one scoring answer, or None if it is unusable."""
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("rubric"), dict):
        raw = raw["rubric"]
    out = {}
    for k in criteria:
        c = raw.get(k)
        if not isinstance(c, dict):
            c = {"band": c}
        try:
            band = float(c.get("band"))
        except (TypeError, ValueError):
            return None
        out[k] = (min(9.0, max(0.0, band)), str(c.get("comment", "")))
    return out


def combine_score_runs(runs: List[dict], criteria=CRITERIA) -> dict:
    """{criterion: CriterionScore} with the median band across runs; the comment comes from a run near it."""
    parts = {}
    for k in criteria:
        bands = [r[k][0] for r in runs]
        median = half_band(statistics.median(bands))
        closest = min(runs, key=lambda r: abs(r[k][0] - median))
        parts[k] = CriterionScore(band=median, comment=closest[k][1], spread=max(bands) - min(bands))
    return parts


def build_rubric(parts: dict) -> EssayRubric:
    return EssayRubric(**parts, overall_band=ielts_overall([parts[k].band for k in CRITERIA]))


def parse_argument(raw: dict) -> ArgumentFeedback:
    comments = []
    for c in raw.get("paragraph_comments") or []:
        try:
            comments.append(ParagraphComment(paragraph=int(c.get("paragraph", 0)), comment=str(c.get("comment", ""))))
        except (TypeError, ValueError, AttributeError):
            continue
    return ArgumentFeedback(
        thesis=str(raw.get("thesis", "")),
        strongest_point=str(raw.get("strongest_point", "")),
        weakest_point=str(raw.get("weakest_point", "")),
        missing_counterargument=str(raw.get("missing_counterargument", "")),
        paragraph_comments=comments,
    )


class GeminiError(RuntimeError):
    """Raised when the AI review could not be produced. Never replaced with fake results."""


class GeminiService:
    def __init__(self):
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    async def _generate_json(self, prompt: str, temperature: float, thinking_budget: int = 0,
                             label: str = "", essay_id: str = "") -> dict:
        """Call Gemini in JSON mode; a response that is not valid JSON is retried once.

        When label is given, the call's time and token counts are appended to the metrics file.
        """
        for attempt in range(2):
            started = time.monotonic()
            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
                )
            )
            if label:
                usage = getattr(response, "usage_metadata", None)
                record_metric({
                    "label": label, "essay_id": essay_id, "attempt": attempt + 1,
                    "seconds": round(time.monotonic() - started, 2),
                    "input_tokens": getattr(usage, "prompt_token_count", None),
                    "output_tokens": getattr(usage, "candidates_token_count", None),
                    "thinking_tokens": getattr(usage, "thoughts_token_count", None),
                    "model": settings.GEMINI_MODEL,
                })
            try:
                return json.loads(response.text or "{}")
            except json.JSONDecodeError:
                if attempt == 1:
                    raise
                logger.warning("Gemini returned malformed JSON; retrying once")

    def _find_exact_offsets(self, text: str, phrase: str, existing_spans: List[tuple],
                            start: int = 0, end: Optional[int] = None) -> tuple[int, int]:
        """Offsets of the first occurrence of phrase in text[start:end] that does not overlap existing spans."""
        if not phrase or not text:
            return -1, -1
        end = len(text) if end is None else end
        window = text[start:end]
        for flags in (0, re.IGNORECASE):
            for match in re.finditer(re.escape(phrase), window, flags):
                idx, stop = start + match.start(), start + match.end()
                if not any(not (stop <= s or idx >= e) for s, e in existing_spans):
                    return idx, stop
        return -1, -1

    def _locate(self, content: str, spans: List[tuple], sentence, phrase: str,
                matched: List[tuple]) -> tuple[int, int]:
        """Position of a candidate: inside its numbered sentence, or anywhere if the phrase is unique."""
        try:
            n = int(sentence)
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= len(spans):
            a, b = spans[n - 1]
            return self._find_exact_offsets(content, phrase, matched, a, b)
        # No usable sentence number: only a phrase that occurs once can be pinned down.
        if content.count(phrase) != 1:
            return -1, -1
        return self._find_exact_offsets(content, phrase, matched)

    def _candidates(self, content: str, spans: List[tuple], raw: list) -> tuple[List[SuggestionItem], int]:
        """Turn detected errors into located suggestions (ids c1, c2, ...). Returns (located, dropped)."""
        located: List[SuggestionItem] = []
        matched: List[tuple] = []
        dropped = 0
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            orig = str(item.get("original_phrase", "")).strip()
            suggested = str(item.get("suggested_phrase", "")).strip()
            # Phrase-level fixes only; no-op edits and contraction expansions are not corrections.
            if not orig or len(orig.split()) > MAX_SUGGESTION_WORDS:
                dropped += 1
                continue
            if suggested == orig or is_contraction_only(orig, suggested):
                continue
            start_idx, end_idx = self._locate(content, spans, item.get("sentence"), orig, matched)
            if start_idx == -1:
                dropped += 1  # not in that sentence: cannot be applied and may be hallucinated
                continue
            matched.append((start_idx, end_idx))

            cat = item.get("category", "Grammar")
            if cat not in ["Grammar", "Spelling", "Clarity", "Natural Expression", "Vocabulary"]:
                cat = "Grammar"
            tier = item.get("tier", "accuracy")
            if tier not in ["accuracy", "idiom", "style"]:
                tier = ("accuracy" if cat in ["Grammar", "Spelling"]
                        else "idiom" if cat in ["Vocabulary", "Natural Expression"] else "style")

            located.append(SuggestionItem(
                id=f"c{len(located) + 1}",
                original_phrase=content[start_idx:end_idx],
                suggested_phrase=suggested,
                category=cat,
                subcategory=item.get("subcategory", "기타 문법"),
                tier=tier,
                explanation=item.get("explanation", ""),
                start_idx=start_idx,
                end_idx=end_idx,
                is_applied=False,
            ))
        return located, dropped

    async def _verify(self, essay_id: str, prompt_text: str, content: str, spans: List[tuple],
                      candidates: List[SuggestionItem]) -> tuple[List[SuggestionItem], List[RecurringPattern], bool]:
        """Keep only the candidates the verifier accepts and group them into patterns.

        Returns (kept, patterns, verified). If the verifier answer is unusable, all candidates are
        kept and verified is False, so a failed check never silently wipes the corrections.
        """
        if not candidates:
            return [], [], True
        try:
            data = await self._generate_json(build_verify_prompt(prompt_text, content, spans, candidates), 0,
                                             thinking_budget=VERIFY_THINKING_BUDGET, label="verify", essay_id=essay_id)
        except Exception as e:
            logger.warning(f"Verification call failed; keeping unverified candidates: {e}")
            return candidates, [], False
        verdicts = data.get("verdicts") if isinstance(data, dict) else None
        if not isinstance(verdicts, list):
            logger.warning("Verification answer had no verdicts; keeping unverified candidates")
            return candidates, [], False

        accepted = {str(v.get("id")) for v in verdicts if isinstance(v, dict) and v.get("valid") is True}
        kept = [c for c in candidates if c.id in accepted]
        by_id = {c.id: c for c in kept}

        patterns: List[RecurringPattern] = []
        for p in data.get("patterns") or []:
            if not isinstance(p, dict) or not str(p.get("pattern", "")).strip():
                continue
            raw_ids = p.get("ids") or []
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            ids = []
            for i in raw_ids:
                i = str(i)
                if i in by_id and i not in ids:
                    ids.append(i)
            if len(ids) < 2:
                continue  # a pattern needs at least two verified corrections behind it
            patterns.append(RecurringPattern(
                pattern=str(p["pattern"]).strip(),
                count=len(ids),
                examples=[by_id[i].original_phrase for i in ids],
                fix=str(p.get("fix", "")),
                tip=str(p.get("tip", "")),
            ))
        return kept, patterns[:4], True

    async def _find_errors(self, essay_id: str, prompt_text: str, content: str, spans: List[tuple]):
        data = await self._generate_json(build_detect_prompt(prompt_text, content, spans), 0,
                                         thinking_budget=DETECT_THINKING_BUDGET, label="detect", essay_id=essay_id)
        candidates, dropped = self._candidates(content, spans, data.get("suggestions"))
        kept, patterns, verified = await self._verify(essay_id, prompt_text, content, spans, candidates)
        return candidates, dropped, kept, patterns, verified

    async def _score(self, essay_id: str, prompt: str, label: str, criteria) -> dict:
        """Score SCORE_RUNS times in parallel and keep the median per criterion; failed runs are skipped."""
        answers = await asyncio.gather(*[
            self._generate_json(prompt, SCORE_TEMPERATURE, thinking_budget=SCORE_THINKING_BUDGET,
                                label=label, essay_id=essay_id)
            for _ in range(SCORE_RUNS)
        ], return_exceptions=True)
        runs = [r for r in (parse_score_run(a, criteria) for a in answers if not isinstance(a, BaseException)) if r]
        if not runs:
            raise GeminiError(f"밴드 채점({label}) 응답을 하나도 받지 못했습니다.")
        if len(runs) < SCORE_RUNS:
            logger.warning(f"Only {len(runs)}/{SCORE_RUNS} {label} runs were usable")
        return combine_score_runs(runs, criteria)

    def _feedback(self, data: dict) -> dict:
        """The main call's output: everything except corrections and bands."""
        key_exprs = [
            KeyExpression(
                expression=normalize_vocab_placeholders(k.get("expression", "").strip()),
                meaning=k.get("meaning", "").strip(),
                pos=(k.get("pos") or "idiom").strip(),
                synonyms=k.get("synonyms", "").strip(),
                example=clean_vocab_example(k.get("example", "").strip()),
                explanation=k.get("explanation", "").strip()
            )
            for k in data.get("key_expressions", [])
            if isinstance(k, dict) and k.get("expression")
        ]
        return {
            "overall_feedback": data.get("overall_feedback", ""),
            "argument": parse_argument(data.get("argument") or {}),
            "revision_focus": [str(x) for x in (data.get("revision_focus") or []) if str(x).strip()][:3],
            "upgraded_text": data.get("upgraded_text") or "",
            "key_expressions": key_exprs,
        }

    async def review_essay_events(self, essay_id: str, prompt_text: str, essay_type: str, content: str):
        """Reviews an essay, yielding (event, data) as each part finishes; the last item is ("done", review).

        Three branches run at the same time:
        - content_scores: task_response and coherence from the essay (three runs, median);
        - feedback: argument feedback, revision focus, the C1+ rewrite and key expressions;
        - corrections: find errors sentence by sentence -> verify each -> group verified ones into patterns,
          then language_scores: grammar and lexical from the verified corrections (three runs, median).
        Sentence pairs and the corrected full text are not generated by the model
        (see generate_sentence_pairs / apply_suggestions). Any failure raises GeminiError.
        """
        type_guide = ESSAY_TYPE_GUIDE.get(essay_type, ESSAY_TYPE_GUIDE["free"])
        spans = split_sentences(content)
        started = time.monotonic()
        queue: asyncio.Queue = asyncio.Queue()
        stats = {}

        async def feedback_branch():
            data = await self._generate_json(build_main_prompt(type_guide, prompt_text, content), 0,
                                             thinking_budget=REVIEW_THINKING_BUDGET, label="main", essay_id=essay_id)
            await queue.put(("feedback", self._feedback(data)))

        async def content_branch():
            scores = await self._score(essay_id, build_content_score_prompt(type_guide, prompt_text, content),
                                       "score_content", CONTENT_CRITERIA)
            await queue.put(("content_scores", scores))

        async def errors_branch():
            candidates, dropped, kept, patterns, verified = await self._find_errors(essay_id, prompt_text, content, spans)
            stats.update(candidates=len(candidates), dropped=dropped)
            kept.sort(key=lambda s: s.start_idx)
            await queue.put(("corrections", {
                "suggestions": kept,
                "recurring_patterns": patterns,
                "corrected_text": apply_suggestions(content, kept),
                "suggestions_verified": verified,
            }))
            language = await self._score(essay_id, build_language_score_prompt(type_guide, prompt_text, content, kept),
                                         "score_language", LANGUAGE_CRITERIA)
            await queue.put(("language_scores", language))

        def guarded(branch):
            async def run():
                try:
                    await branch()
                except Exception as e:  # reported through the queue so the consumer stops at once
                    await queue.put(("_error", e))
            return run

        tasks = [asyncio.create_task(guarded(b)()) for b in (feedback_branch, content_branch, errors_branch)]
        parts = {}
        try:
            while len(parts) < 4:
                event, data = await queue.get()
                if event == "_error":
                    logger.error(f"Gemini review error: {data}", exc_info=data)
                    raise GeminiError(str(data)) from data
                parts[event] = data
                yield event, data
        finally:
            for t in tasks:
                t.cancel()

        corrections, feedback = parts["corrections"], parts["feedback"]
        suggestions = corrections["suggestions"]
        for s in suggestions:
            s.id = str(uuid.uuid4())[:8]
        record_metric({
            "label": "summary", "essay_id": essay_id, "seconds": round(time.monotonic() - started, 2),
            "sentences": len(spans), "candidates": stats["candidates"], "dropped_unlocated": stats["dropped"],
            "kept": len(suggestions),
            "rejected": stats["candidates"] - len(suggestions) if corrections["suggestions_verified"] else 0,
            "patterns": len(corrections["recurring_patterns"]), "verified": corrections["suggestions_verified"],
        })
        yield "done", ReviewResponse(
            essay_id=essay_id,
            original_text=content,
            corrected_text=corrections["corrected_text"],
            upgraded_text=feedback["upgraded_text"] or corrections["corrected_text"],
            overall_feedback=feedback["overall_feedback"],
            rubric=build_rubric({**parts["content_scores"], **parts["language_scores"]}),
            argument=feedback["argument"],
            revision_focus=feedback["revision_focus"],
            recurring_patterns=corrections["recurring_patterns"],
            suggestions=suggestions,
            sentence_pairs=[],
            key_expressions=feedback["key_expressions"],
            suggestions_verified=corrections["suggestions_verified"],
        )

    async def review_essay(self, essay_id: str, prompt_text: str, essay_type: str, content: str) -> ReviewResponse:
        """The whole review at once (see review_essay_events)."""
        async for event, data in self.review_essay_events(essay_id, prompt_text, essay_type, content):
            if event == "done":
                return data
        raise GeminiError("review ended without a result")

    async def generate_sentence_pairs(self, review: ReviewResponse) -> List[SentencePair]:
        """Sentence-by-sentence study pairs, generated only when the user opens that tab.

        original/corrected come from code (the stored suggestions); the model only aligns each
        sentence with the upgraded version and adds a translation, a short note and up to 3 words.
        """
        text = review.original_text
        spans = split_sentences(text)
        rows = []
        for i, (a, b) in enumerate(spans, start=1):
            rows.append({"index": i, "original": text[a:b],
                         "corrected": apply_suggestions(text, review.suggestions, start=a, end=b)})
        if not rows:
            return []

        listing = "\n".join(f'{r["index"]}. {r["corrected"]}' for r in rows)
        prompt = f"""
아래는 학습자 문장(교정본) 목록과 같은 내용을 C1+ 수준으로 다시 쓴 글입니다. 문장 번호마다 다음을 JSON으로 주세요.
- native: 다시 쓴 글에서 그 문장에 대응하는 부분(한두 문장, 다시 쓴 글의 문장을 그대로 사용)
- translation: native의 자연스러운 한국어 번역
- explanation: 교정본과 native의 핵심 차이 한국어 한 문장
- vocab: native에서 배울 만한 단어·표현 최대 3개 (word, meaning(한국어), pos)

{{"pairs": [{{"index": 1, "native": "...", "translation": "...", "explanation": "...", "vocab": [{{"word": "...", "meaning": "...", "pos": "v"}}]}}]}}

[학습자 문장]
{listing}

[다시 쓴 글]
{review.upgraded_text}
"""
        try:
            data = await self._generate_json(prompt, 0.2)
        except Exception as e:
            logger.error(f"Sentence pair generation error: {e}", exc_info=True)
            raise GeminiError(str(e)) from e

        by_index = {}
        for p in data.get("pairs", []):
            try:
                by_index[int(p.get("index"))] = p
            except (TypeError, ValueError):
                continue
        pairs = []
        for r in rows:
            p = by_index.get(r["index"], {})
            pairs.append(SentencePair(
                id=f"S{r['index']}",
                index=r["index"],
                original=r["original"],
                corrected=r["corrected"],
                native=(p.get("native") or r["corrected"]).strip(),
                translation=(p.get("translation") or "").strip(),
                explanation=(p.get("explanation") or "").strip(),
                vocab=[VocabItem(word=v.get("word", ""), meaning=v.get("meaning", ""), pos=v.get("pos", ""))
                       for v in (p.get("vocab") or [])[:3] if isinstance(v, dict) and v.get("word")],
            ))
        return pairs

    async def lookup_word(self, word: str, context: str = "") -> dict:
        """Instant dictionary lookup adhering to Anki Manager / Shadowing Player standards."""
        raw_word = word.strip()
        cleaned_word = re.sub(r"^[^\w\s'-]+|[^\w\s'-]+$", "", raw_word).strip()
        if not cleaned_word:
            cleaned_word = raw_word
        norm_word = normalize_vocab_placeholders(cleaned_word)

        prompt = f"""
당신은 Anki Manager의 전문 어휘 학습 강사입니다.
문맥 "{context}" 속 영단어/숙어/표현 "{norm_word}"를 분석하여 JSON 객체를 반환하십시오.

[작성 규칙 (Anki Manager 4대 원칙)]:
1. "word": 원본 영단어 또는 숙어 (A, B, V, V-ing 등의 표준 플레이스홀더 사용: 예 'look forward to V-ing', 'spring A on B')
2. "phonetic": IPA 발음기호 (숙어나 긴 구문이면 "-")
3. "pos": 품사 ("n", "v", "adj", "adv", "idiom", "prep", "conj" 중 하나)
4. "meaning": 문맥에 맞는 정확하고 자연스러운 한국어 뜻
5. "explanation": Anki Manager 3단계 공식 엄수 (3~4문장):
   - ① 의미/뉘앙스: "[단어]는 '[뜻]'이라는 의미로, [구체적 쓰임새]를 나타냅니다."
   - ② 유의어 비교: "[유의어]와 비슷하지만, [단어]는 [차이점]을 강조합니다."
   - ③ 콜로케이션: "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다."
6. "synonyms": 2~4개의 영단어/유의어 (쉼표 구분)
7. "example": 해당 표현이 사용된 자연스러운 실용 영어 예문 (단어에 A, B가 있다면 예문에서는 실제 문맥에 맞는 단어로 대체할 것. 괄호나 한국어 번역은 절대 넣지 말고 100% 순수 영어 문장으로만 작성할 것)

반드시 유효한 JSON 형식으로만 응답하십시오.
"""
        try:
            data = await self._generate_json(prompt, 0.2)
            return {
                "word": data.get("word", norm_word),
                "phonetic": data.get("phonetic", ""),
                "pos": data.get("pos", "idiom"),
                "meaning": data.get("meaning", "한국어 뜻 분석 중"),
                "explanation": data.get("explanation", ""),
                "synonyms": data.get("synonyms", ""),
                "example": clean_vocab_example(data.get("example", ""))
            }
        except Exception as e:
            logger.error(f"Lookup error for {word}: {e}")
            return {
                "word": norm_word,
                "phonetic": "",
                "pos": "idiom",
                "meaning": "",
                "explanation": "",
                "synonyms": "",
                "example": ""
            }

    async def generate_anki_card_preview(self, card_type: CardType, text: str, context: str = "") -> CardPreviewResponse:
        """Enriches a sentence or vocabulary item for Anki card creation."""
        if card_type == "sentence":
            prompt = f"""
다음 영어 문장에 대한 정확하고 자연스러운 한국어 해석과 핵심 문법/표현 해설을 작성해주세요.

[영어 문장]: {text}
[문맥/배경]: {context}

JSON 응답 규격:
{{
  "translation": "자연스러운 한국어 번역",
  "explanation": "문법 및 표현 포인트 해설 (간결하게 1~2문장)"
}}
"""
            try:
                res = await self._generate_json(prompt, 0.2)
                return CardPreviewResponse(
                    card_type="sentence",
                    deck_name="1. Language::1.1. English::Sentence",
                    model_name="English Sentence",
                    front=text.strip(),
                    meaning=res.get("translation", ""),
                    explanation=res.get("explanation", ""),
                    example="",
                    pos="",
                    synonyms=""
                )
            except Exception as e:
                logger.error(f"Error generating sentence preview: {e}")
                return CardPreviewResponse(
                    card_type="sentence",
                    deck_name="1. Language::1.1. English::Sentence",
                    model_name="English Sentence",
                    front=text.strip(),
                    meaning="",
                    explanation="",
                    example="",
                    pos="",
                    synonyms=""
                )

        else: # vocab
            norm_text = normalize_vocab_placeholders(text.strip())
            prompt = f"""
다음 영어 단어/숙어에 대해 Anki Manager 규격에 맞춘 전문 단어 카드 정보를 작성해주세요.

[단어/숙어]: {norm_text}
[문맥]: {context}

[작성 규칙]:
1. "front": 표준화된 표제어 (someone/something 대신 A, B, V-ing 기호 적용: 예 'spring A on B', 'look forward to V-ing')
2. "meaning": 문맥에 맞는 자연스러운 한국어 뜻
3. "pos": 품사 ("n", "v", "adj", "adv", "idiom", "prep", "conj" 중 하나)
4. "synonyms": 2~3개의 유의어 (쉼표 구분)
5. "example": 100% 순수 영어 예문 (A, B는 실제 구체적인 단어로 치환. 괄호나 한국어 해석 절대 금지)
6. "explanation": Anki Manager 3단계 공식 엄수 (3~4문장):
   - ① 의미/뉘앙스: "[단어]는 '[뜻]'이라는 의미로, [구체적 쓰임새]를 나타냅니다."
   - ② 유의어 비교: "[유의어]와 비슷하지만, [단어]는 [차이점]을 강조합니다."
   - ③ 콜로케이션: "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다."

JSON 응답 규격:
{{
  "front": "{norm_text}",
  "meaning": "...",
  "pos": "idiom",
  "synonyms": "...",
  "example": "...",
  "explanation": "..."
}}
"""
            try:
                res = await self._generate_json(prompt, 0.2)
                return CardPreviewResponse(
                    card_type="vocab",
                    deck_name="1. Language::1.1. English::Vocabulary",
                    model_name="English Vocabulary",
                    front=res.get("front", norm_text),
                    meaning=res.get("meaning", ""),
                    explanation=res.get("explanation", ""),
                    example=clean_vocab_example(res.get("example", "")),
                    pos=res.get("pos", "idiom"),
                    synonyms=res.get("synonyms", "")
                )
            except Exception as e:
                logger.error(f"Error generating vocab preview: {e}")
                return CardPreviewResponse(
                    card_type="vocab",
                    deck_name="1. Language::1.1. English::Vocabulary",
                    model_name="English Vocabulary",
                    front=norm_text,
                    meaning="",
                    explanation="",
                    example="",
                    pos="",
                    synonyms=""
                )

gemini_service = GeminiService()
