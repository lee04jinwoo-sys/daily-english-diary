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
    EssayRubric, CriterionScore, ArgumentFeedback, ParagraphComment,
)
from app.schemas.anki import CardPreviewResponse, CardType

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
        """Reviews an argumentative essay: IELTS-style 4-criterion bands, argument-level feedback,
        inline fixes, and a C1+ rewrite that keeps the writer's own argument."""
        type_guide = ESSAY_TYPE_GUIDE.get(essay_type, ESSAY_TYPE_GUIDE["free"])
        prompt = f"""
당신은 IELTS Writing Task 2 채점 경험이 많은 영어 작문 코치이자 Anki 어휘 제작 전문가입니다.
학습자는 토플 100점 수준(B2~C1)의 한국인입니다. 칭찬보다 다음 단계로 올라가기 위한 구체적이고 냉정한 피드백을 주세요.

[에세이 문제]: {prompt_text}
[에세이 유형]: {type_guide}
[학습자 에세이]:
\"\"\"{content}\"\"\"

[채점 원칙]
1. rubric: IELTS Task 2의 4개 기준으로 각각 0~9 밴드(0.5 단위)와 한국어 한 줄 코멘트를 줍니다.
   - task_response: 문제에 정확히 답했는가, 입장이 분명하고 끝까지 일관되는가, 근거가 충분히 전개되었는가
   - coherence: 문단 구성, 논리 흐름, 연결어의 자연스러운 사용(남용 포함)
   - lexical: 어휘의 정확성·폭·콜로케이션
   - grammar: 문법 정확성과 복문·양보·가정 등 구조의 다양성
   - overall_band: 4개 평균을 0.5 단위로 반올림
   - 분량이 짧으면 task_response를 그에 맞게 낮게 주되, 분량 자체를 나무라지는 마세요(분량은 학습자 자유).
2. argument: 논증 수준의 피드백(한국어).
   - thesis: 입장이 얼마나 분명하고 논쟁 가능한가
   - strongest_point: 가장 설득력 있는 부분
   - weakest_point: 가장 약한 논거와 구체적인 보강 방법
   - missing_counterargument: 다뤘어야 할 반론과 그에 대한 재반박 방향(이미 잘 다뤘다면 그렇다고 쓰기)
   - paragraph_comments: 문단 번호(1부터)별 한 줄 코멘트
3. revision_focus: 고쳐 쓸 때 집중할 2~3가지(한국어, 각 한 문장, 실행 가능한 지시).
4. corrected_text: 학습자의 구조와 논지를 그대로 두고 문법·철자·명백한 오류만 고친 전문.
5. upgraded_text: 같은 입장·같은 논거로 C1+ 필자가 썼을 법한 버전. 문단 구조는 유지하되 논리 연결, 정확한 어휘,
   양보/반박 구조를 보강합니다. 기준 문체는 좋은 신문 칼럼(예: The Economist)처럼 정확하고 담백한 논증문입니다.
   - 금지: 미사여구, 과장된 형용사(formidable, exorbitant 등을 습관적으로 쓰기), IELTS 템플릿 상투구
     (foster an environment conducive to, it is undeniable that, in this day and age, plays a pivotal role 등).
6. suggestions (인라인 교정, tier 필수):
   - "accuracy": 틀린 문법/철자/관사/수일치/시제 등 명백한 오류만
   - "idiom": 문법은 맞지만 어색한 직역투, 부정확한 단어 선택, 더 정확한 콜로케이션
   - "style": 논증문에 더 맞는 표현, 연결어 다양화, 격식 조정(선택 사항)
   - 모든 tier 공통: original_phrase는 원문에 그대로 있는 2~7단어 구문만. 문장 전체를 바꾸는 제안은 금지합니다.
     문장 단위 재구성은 upgraded_text와 sentence_pairs의 native에서만 보여주세요.
   - suggested_phrase는 학습자의 단어를 최대한 살린 최소 수정이어야 합니다
     (예: 'make companies to allow' -> 'make companies allow' 또는 'require companies to allow').
7. sentence_pairs: 문장별 original / corrected / native(= upgraded 버전의 대응 문장) / translation(한국어) / explanation(한국어) / vocab.
8. key_expressions: upgraded_text에서 학습자가 다음 에세이에 바로 쓸 만한 논증 표현·콜로케이션 4~8개.
   - 표기 표준화: someone/something/sb/sth 대신 A, B, C 및 V-ing (예: 'attribute A to B')
   - pos: "n", "v", "adj", "adv", "idiom", "prep", "conj" 중 하나
   - synonyms: 2~3개 (쉼표 구분)
   - example: 100% 영어 예문(A, B는 실제 단어로 치환, 괄호·한국어 금지)
   - explanation: 3단계 공식(3~4문장) ① 의미/뉘앙스 ② 유의어 비교 ③ 콜로케이션 '[영어표현](한글뜻)'

[JSON 응답 규격]
{{
  "corrected_text": "...",
  "upgraded_text": "...",
  "overall_feedback": "총평 한국어 3문장: 현재 수준, 가장 큰 약점, 다음 한 걸음",
  "rubric": {{
    "task_response": {{"band": 6.5, "comment": "..."}},
    "coherence": {{"band": 6.5, "comment": "..."}},
    "lexical": {{"band": 7.0, "comment": "..."}},
    "grammar": {{"band": 6.5, "comment": "..."}},
    "overall_band": 6.5
  }},
  "argument": {{
    "thesis": "...", "strongest_point": "...", "weakest_point": "...", "missing_counterargument": "...",
    "paragraph_comments": [{{"paragraph": 1, "comment": "..."}}]
  }},
  "revision_focus": ["...", "..."],
  "suggestions": [{{"original_phrase": "...", "suggested_phrase": "...", "tier": "accuracy", "category": "Grammar", "subcategory": "관사(Article)", "explanation": "..."}}],
  "sentence_pairs": [{{"original": "...", "corrected": "...", "native": "...", "translation": "...", "explanation": "...", "vocab": [{{"word": "...", "meaning": "...", "pos": "v"}}]}}],
  "key_expressions": [{{"expression": "...", "meaning": "...", "pos": "idiom", "synonyms": "...", "example": "...", "explanation": "..."}}]
}}
"""
        try:
            data = await self._generate_json(prompt, 0.3, thinking_budget=1024)

            # Process suggestions
            processed_suggestions: List[SuggestionItem] = []
            matched_spans: List[tuple] = []

            for item in data.get("suggestions", []):
                orig = item.get("original_phrase", "").strip()
                # Inline suggestions are phrase-level fixes; sentence rewrites belong in upgraded_text.
                if not orig or len(orig.split()) > MAX_SUGGESTION_WORDS:
                    continue
                start_idx, end_idx = self._find_exact_offsets(content, orig, matched_spans)
                if start_idx != -1:
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
                    suggested_phrase=item.get("suggested_phrase", ""),
                    category=cat,
                    subcategory=item.get("subcategory", "기타 문법"),
                    tier=tier,
                    explanation=item.get("explanation", ""),
                    start_idx=start_idx,
                    end_idx=end_idx,
                    is_applied=False
                ))

            # Sort suggestions by start_idx
            processed_suggestions.sort(key=lambda s: s.start_idx if s.start_idx != -1 else 999999)

            # Process sentence pairs
            sentence_pairs: List[SentencePair] = []
            raw_pairs = data.get("sentence_pairs", [])
            for idx, sp in enumerate(raw_pairs, start=1):
                vocab_list = [
                    VocabItem(
                        word=v.get("word", ""),
                        meaning=v.get("meaning", ""),
                        pos=v.get("pos", "")
                    )
                    for v in sp.get("vocab", [])
                    if v.get("word")
                ]
                orig_s = sp.get("original", "").strip()
                corr_s = sp.get("corrected", "").strip() or orig_s
                nat_s = sp.get("native", "").strip() or corr_s

                sentence_pairs.append(SentencePair(
                    id=f"S{idx}",
                    index=idx,
                    original=orig_s,
                    corrected=corr_s,
                    native=nat_s,
                    translation=sp.get("translation", "").strip(),
                    explanation=sp.get("explanation", "").strip(),
                    vocab=vocab_list
                ))

            key_exprs = [
                KeyExpression(
                    expression=normalize_vocab_placeholders(k.get("expression", "").strip()),
                    meaning=k.get("meaning", "").strip(),
                    pos=k.get("pos", "idiom").strip(),
                    synonyms=k.get("synonyms", "").strip(),
                    example=clean_vocab_example(k.get("example", "").strip()),
                    explanation=k.get("explanation", "").strip()
                )
                for k in data.get("key_expressions", [])
                if k.get("expression")
            ]

            return ReviewResponse(
                essay_id=essay_id,
                original_text=content,
                corrected_text=data.get("corrected_text") or content,
                upgraded_text=data.get("upgraded_text") or data.get("corrected_text") or content,
                overall_feedback=data.get("overall_feedback", ""),
                rubric=parse_rubric(data.get("rubric") or {}),
                argument=parse_argument(data.get("argument") or {}),
                revision_focus=[str(x) for x in (data.get("revision_focus") or []) if str(x).strip()][:3],
                suggestions=processed_suggestions,
                sentence_pairs=sentence_pairs,
                key_expressions=key_exprs
            )

        except Exception as e:
            logger.error(f"Gemini review error: {e}", exc_info=True)
            raise GeminiError(str(e)) from e

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
