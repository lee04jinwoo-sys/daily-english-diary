import json
import logging
import re
import uuid
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


def round_band(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(9.0, max(0.0, round(v * 2) / 2))


def parse_rubric(raw: dict) -> EssayRubric:
    def crit(key: str) -> CriterionScore:
        c = raw.get(key) or {}
        if not isinstance(c, dict):
            c = {"band": c}
        return CriterionScore(band=round_band(c.get("band")), comment=str(c.get("comment", "")))

    parts = {k: crit(k) for k in ("task_response", "coherence", "lexical", "grammar")}
    overall = raw.get("overall_band")
    if overall is None:
        overall = sum(p.band for p in parts.values()) / 4
    return EssayRubric(**parts, overall_band=round_band(overall))


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

    async def _generate_json(self, prompt: str, temperature: float, thinking_budget: int = 0) -> dict:
        response = await self.client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
            )
        )
        return json.loads(response.text or "{}")

    def _find_exact_offsets(self, text: str, phrase: str, existing_spans: List[tuple]) -> tuple[int, int]:
        """Locates the exact start and end char offsets of a phrase in text without overlapping."""
        if not phrase or not text:
            return -1, -1
        
        start = 0
        while True:
            idx = text.find(phrase, start)
            if idx == -1:
                break
            end = idx + len(phrase)
            overlap = any(not (end <= s or idx >= e) for s, e in existing_spans)
            if not overlap:
                return idx, end
            start = idx + 1
        
        pattern = re.escape(phrase)
        for match in re.finditer(pattern, text, re.IGNORECASE):
            idx, end = match.start(), match.end()
            overlap = any(not (end <= s or idx >= e) for s, e in existing_spans)
            if not overlap:
                return idx, end

        return -1, -1

    async def review_essay(self, essay_id: str, prompt_text: str, essay_type: str, content: str) -> ReviewResponse:
        """Reviews an essay for output practice: bands, recurring patterns, inline fixes, a C1+ rewrite.

        Sentence-by-sentence pairs and the corrected full text are not generated here
        (see generate_sentence_pairs / apply_suggestions), which keeps the output small.
        """
        type_guide = ESSAY_TYPE_GUIDE.get(essay_type, ESSAY_TYPE_GUIDE["free"])
        # Static instructions first and the essay last, so the shared prefix can be cached.
        prompt = f"""
당신은 IELTS Writing Task 2 채점 경험이 많은 영어 코치입니다. 학습자는 토플 100점 수준(B2~C1)의 한국인입니다.
이 연습의 목적은 형식을 갖춘 글쓰기가 아니라 **영어 출력**, 즉 자기 생각을 영어로 정확하고 자연스럽게 꺼내는 능력입니다.
서론·결론 유무, 문단 형식, 분량은 감점하지도 지적하지도 않습니다. 피드백의 중심은 언어입니다. 칭찬보다 구체적이고 냉정하게.

[점검 절차] 답을 쓰기 전에 에세이를 첫 문장부터 마지막 문장까지 한 문장씩 점검하세요.
문장마다 주어-동사 수일치, 관사(가산명사 단수, the internet처럼 관용적으로 the가 붙는 명사), 동사 형태(to부정사/동명사,
사역·지각동사 구문), 전치사, 단어 선택(한국어 직역)을 확인하고, 발견한 오류는 하나도 빠짐없이 suggestions에 넣습니다.

[출력 지침]
1. rubric: IELTS 4개 기준 각각 0~9 밴드(0.5 단위) + 한국어 한 줄 코멘트. overall_band는 4개 평균을 0.5 단위로 반올림.
   - task_response: 질문에 답했는가, 하고 싶은 말(입장과 근거)이 분명히 전달되는가
   - coherence: 문장과 아이디어가 자연스럽게 이어지는가, 연결어 사용(남용 포함)
   - lexical: 어휘의 정확성·폭·콜로케이션
   - grammar: 문법 정확성과 구조의 다양성
2. argument (한국어, 각 1~2문장): thesis, strongest_point, weakest_point, missing_counterargument,
   paragraph_comments(문단 번호별 한 줄). 학습자의 예시가 자기 주장과 모순되면 weakest_point에서 그것부터 지적하세요.
3. recurring_patterns: 같은 오류·한국어 직역 습관이 2번 이상 나오면 묶습니다(최대 4개, 많은 순, 없으면 []).
   '관사 오류', '직역투' 같은 넓은 범주가 아니라 구체적인 단어·구조 단위로 묶으세요
   (예: "privacy를 '사생활 내용'의 뜻으로 사용", "'the famous'를 사람 명사로 반복", "가산명사 life 단수에 관사 누락").
   pattern(한국어 이름), count(실제 횟수), examples(원문에 그대로 있는 구문), fix(영어), tip(한국어 한 문장).
4. revision_focus: 고쳐 쓸 때 집중할 표현상의 2~3가지(한국어, 각 한 문장).
5. suggestions (tier 필수):
   - "accuracy": 명백한 오류 / "idiom": 어색한 직역투·부정확한 단어·콜로케이션 / "style": 더 자연스러운 표현(선택)
   - original_phrase는 원문에 글자 그대로 있는 2~7단어 구문이며, 에세이 안에서 한 번만 나와야 합니다.
     같은 단어가 여러 번 나오면 앞뒤 단어를 붙여 위치를 특정하세요(예: 'internet' 대신 'social media and internet').
     문장 전체를 바꾸는 제안 금지.
   - suggested_phrase는 학습자의 단어를 살린 최소 수정이며, 같은 오류가 남아 있으면 안 됩니다.
   - 같은 오류가 여러 번 나오면 나올 때마다 각각 만드세요. 축약형 풀기·격식 조정 제안은 하지 마세요.
   - explanation은 한국어 한 문장.
6. upgraded_text: 같은 입장·논거로 C1+ 필자가 쓴 버전. 좋은 신문 칼럼처럼 정확하고 담백하게.
   미사여구, 과장된 형용사, IELTS 상투구(foster an environment conducive to, it is undeniable that, plays a pivotal role 등) 금지.
7. key_expressions: upgraded_text에서 다음 글에 바로 쓸 표현 4~6개. expression(someone/something 대신 A, B, V-ing 표기),
   meaning(한국어), pos("n","v","adj","adv","idiom","prep","conj" 중 하나)만 쓰세요.
8. overall_feedback: 한국어 2~3문장(현재 수준, 가장 큰 약점, 다음 한 걸음).

[JSON 응답 규격]
{{
  "rubric": {{"task_response": {{"band": 6.5, "comment": "..."}}, "coherence": {{"band": 6.5, "comment": "..."}},
             "lexical": {{"band": 6.5, "comment": "..."}}, "grammar": {{"band": 6.5, "comment": "..."}}, "overall_band": 6.5}},
  "argument": {{"thesis": "...", "strongest_point": "...", "weakest_point": "...", "missing_counterargument": "...",
               "paragraph_comments": [{{"paragraph": 1, "comment": "..."}}]}},
  "recurring_patterns": [{{"pattern": "...", "count": 2, "examples": ["..."], "fix": "...", "tip": "..."}}],
  "revision_focus": ["..."],
  "suggestions": [{{"original_phrase": "...", "suggested_phrase": "...", "tier": "accuracy", "category": "Grammar", "subcategory": "관사(Article)", "explanation": "..."}}],
  "upgraded_text": "...",
  "key_expressions": [{{"expression": "...", "meaning": "...", "pos": "v"}}],
  "overall_feedback": "..."
}}

[에세이 유형]: {type_guide}
[에세이 문제]: {prompt_text}
[학습자 에세이]:
\"\"\"{content}\"\"\"
"""
        try:
            data = await self._generate_json(prompt, 0, thinking_budget=REVIEW_THINKING_BUDGET)

            processed_suggestions: List[SuggestionItem] = []
            matched_spans: List[tuple] = []

            for item in data.get("suggestions", []):
                orig = item.get("original_phrase", "").strip()
                # Inline suggestions are phrase-level fixes; sentence rewrites belong in upgraded_text.
                if not orig or len(orig.split()) > MAX_SUGGESTION_WORDS:
                    continue
                suggested = item.get("suggested_phrase", "").strip()
                # No-op edits and contraction expansions are not corrections in output practice.
                if suggested == orig or is_contraction_only(orig, suggested):
                    continue
                # A phrase that occurs more than once cannot be pinned to one place;
                # applying it to the wrong occurrence would corrupt correct text.
                if content.count(orig) > 1:
                    continue
                start_idx, end_idx = self._find_exact_offsets(content, orig, matched_spans)
                if start_idx == -1:
                    continue  # not in the essay: cannot be applied and may be hallucinated
                matched_spans.append((start_idx, end_idx))

                cat = item.get("category", "Grammar")
                if cat not in ["Grammar", "Spelling", "Clarity", "Natural Expression", "Vocabulary"]:
                    cat = "Grammar"

                tier = item.get("tier", "accuracy")
                if tier not in ["accuracy", "idiom", "style"]:
                    if cat in ["Grammar", "Spelling"]:
                        tier = "accuracy"
                    elif cat in ["Vocabulary", "Natural Expression"]:
                        tier = "idiom"
                    else:
                        tier = "style"

                processed_suggestions.append(SuggestionItem(
                    id=str(uuid.uuid4())[:8],
                    original_phrase=orig,
                    suggested_phrase=suggested,
                    category=cat,
                    subcategory=item.get("subcategory", "기타 문법"),
                    tier=tier,
                    explanation=item.get("explanation", ""),
                    start_idx=start_idx,
                    end_idx=end_idx,
                    is_applied=False
                ))

            processed_suggestions.sort(key=lambda s: s.start_idx)

            patterns = []
            for p in parse_patterns(data.get("recurring_patterns")):
                p.examples = [ex for ex in p.examples if ex in content]
                if p.examples:
                    patterns.append(p)

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
                if k.get("expression")
            ]

            corrected = apply_suggestions(content, processed_suggestions)
            return ReviewResponse(
                essay_id=essay_id,
                original_text=content,
                corrected_text=corrected,
                upgraded_text=data.get("upgraded_text") or corrected,
                overall_feedback=data.get("overall_feedback", ""),
                rubric=parse_rubric(data.get("rubric") or {}),
                argument=parse_argument(data.get("argument") or {}),
                revision_focus=[str(x) for x in (data.get("revision_focus") or []) if str(x).strip()][:3],
                recurring_patterns=patterns,
                suggestions=processed_suggestions,
                sentence_pairs=[],
                key_expressions=key_exprs
            )

        except Exception as e:
            logger.error(f"Gemini review error: {e}", exc_info=True)
            raise GeminiError(str(e)) from e

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
