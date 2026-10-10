import json
import logging
import re
import uuid
from typing import Optional, List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.review import ReviewResponse, SuggestionItem, KeyExpression, SentencePair, VocabItem
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

    async def _generate_json(self, prompt: str, temperature: float) -> dict:
        response = await self.client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
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

    async def review_diary(self, date: str, content: str, title: str = "") -> ReviewResponse:
        """
        Reviews English diary text with Level+1 (i+1) Natural Conversational Polish.
        Maintains user's natural thought structure by 80%+, avoids flowery/novelistic writing,
        and provides practical daily collocations and Anki Manager standard vocabulary.
        """
        prompt = f"""
당신은 한국인 학습자를 위한 친절하고 실용적인 1:1 원어민 영어 튜터이자 Anki 어휘 제작 전문가입니다.
사용자가 작성한 아래 영어 일기를 검토하고, **Level + 1 (i + 1)** 기준으로 첨삭해주세요.

[일기 제목]: {title}
[일기 본문]:
\"\"\"{content}\"\"\"

[⭐⭐⭐ 핵심 첨삭 및 어휘 작성 원칙 ⭐⭐⭐]
1. **과도한 문학적 수식어나 소설 같은 미사여구 절대 금지**:
   - ❌ 나쁜 예: "What a marathon day it was! My epic journey began with...", "I was enveloped by..." (너무 극적이고 소설 같음)
   - ⭕ 좋은 예: "It was such a long day. I took a 10-hour flight from Incheon to LA and had a layover at LAX." (원문의 톤을 살린 자연스러운 원어민 일상 대화체)
2. **사용자의 원래 문장 구조와 생각의 흐름을 80% 이상 유지**:
   - 이미 문법이 맞고 자연스러운 문장은 억지로 바꾸지 말고 그대로 둡니다.
   - 사소한 스타일 차이 때문에 문장을 인위적으로 뜯어고치지 마세요.
3. **첨삭 3-Tier 엄격 분류 (suggestions의 tier 속성 반드시 지정)**:
   - 🔴 **"accuracy" (필수 교정)**:
     - 주어-동사 수일치, 시제 불일치, 동사 누락, 명확한 철자 오류 등 '틀린 문법'만 지정합니다.
     - ⚠️ 금지: 'is not' ➔ 'isn't' 같은 축약형 권장이나 사소한 어조 차이는 절대로 accuracy로 지정하지 마세요!
   - 🟡 **"idiom" (원어민 표현/콜로케이션)**:
     - 문법적으로는 통할 수 있으나 원어민이 실제로 쓰지 않는 어색한 직역투/콩글리시, 자연스러운 구동사(Phrasal Verbs) 및 전치사 조합.
     - 예: 'transit at LA airport' ➔ 'have a layover at LAX', 'after the come and go' ➔ 'after all the back and forth'.
   - 🔵 **"style" (스타일 팁/선택적 제안)**:
     - 문법적으로 완벽히 맞지만 구어체 축약형('is not' ➔ 'isn't'), 자연스러운 문맥 흐름('walking them' ➔ 'out walking them') 등 순수한 취향/스타일 팁.
4. **단문/구문 단위 스팬 엄격 제한 (Atomic Phrase Only)**:
   - 'original_phrase'는 교정이 필요한 핵심 구문(2~7단어 이내)만 정확히 타겟팅하세요.
   - 절대로 15~30단어 이상의 긴 복문 전체를 통째로 하나의 suggestion으로 묶지 마세요.
5. **3단계 문장 대조 (sentence_pairs)**:
   - 일기를 한 문장씩 나누어 3단계(original, corrected, native) 및 한국어 translation, explanation, vocab을 제공하세요.
6. **핵심 추천 표현 (key_expressions) - Anki Manager / Shadowing Player 4대 규칙 100% 엄수**:
   - **단어 표기 표준화**: 숙어/동사구의 대상은 'someone', 'something', 'sb', 'sth' 대신 대문자 'A', 'B', 'C' 및 'V-ing' 기호로 표준화하세요. (예: 'spring A on B', 'prevent A from V-ing')
   - **품사 (pos)**: "n", "v", "adj", "adv", "idiom", "prep", "conj" 중 하나 (소문자 약어)
   - **유의어 (synonyms)**: 2~3개의 영단어 유의어 (쉼표 구분)
   - **예문 (example)**: 해당 표현이 쓰인 100% 순수 영어 문장. (단어에 A, B가 있다면 예문에서는 반드시 실제 자연스러운 구체적 단어로 대체할 것. 괄호나 한국어 해석 절대 금지)
   - **설명 (explanation)**: Anki Manager 3단계 공식 엄수 (3~4문장):
     - ① 의미/뉘앙스: "[단어]는 '[뜻]'이라는 의미로, [구체적 쓰임새]를 나타냅니다."
     - ② 유의어 비교: "[유의어]와 비슷하지만, [단어]는 [차이점]을 강조합니다."
     - ③ 콜로케이션: "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다."

[JSON 응답 규격]:
{{
  "original_text": "{content}",
  "corrected_text": "원문 구조 유지 + 문법/철자만 완벽히 수정한 전체 일기",
  "native_text": "Level+1 자연스러운 실전 일상 표현으로 다듬은 전체 일기",
  "overall_feedback": "일기 내용에 대한 따뜻한 공감과 실전 영어 학습 팁 (한국어 3문장)",
  "followup_question": "일기 내용과 관련된 흥미로운 영어 질문 1문장",
  "score": 85,
  "rubric": {{
    "grammar": "A",
    "vocabulary": "B",
    "naturalness": "A",
    "clarity": "A",
    "overall_grade": "A"
  }},
  "suggestions": [
    {{
      "original_phrase": "원문에서 틀리거나 어색한 정확한 구문 (2~7단어 이내, 끝 마침표 제외)",
      "suggested_phrase": "더 자연스러운 표현 (원문에 마침표가 없으면 마침표 붙이지 말 것)",
      "tier": "accuracy",
      "category": "Grammar",
      "subcategory": "전치사(Preposition)",
      "explanation": "한국어 해설"
    }}
  ],
  "sentence_pairs": [
    {{
      "original": "Yesterday I go to airport.",
      "corrected": "Yesterday I went to the airport.",
      "native": "Yesterday, I headed to the airport.",
      "translation": "어제 저는 공항에 갔습니다.",
      "explanation": "과거 시제이므로 went를 쓰며 the가 필요합니다.",
      "vocab": [
        {{"word": "head to", "meaning": "~로 향하다/가다", "pos": "v"}}
      ]
    }}
  ],
  "key_expressions": [
    {{
      "expression": "look forward to V-ing",
      "meaning": "~하기를 손꼽아 기다리다/기대하다",
      "pos": "idiom",
      "synonyms": "anticipate, await, expect",
      "example": "I'm really looking forward to visiting Toronto this summer.",
      "explanation": "look forward to V-ing는 '~하기를 기대하다'라는 의미로, 미래의 즐거운 일을 고대할 때 쓰입니다. expect와 비슷하지만, look forward to V-ing는 설레는 감정이 강조됩니다. 자주 쓰이는 표현으로는 'look forward to hearing from you(답장을 기다리겠습니다)' 등이 있습니다."
    }}
  ]
}}
"""
        try:
            data = await self._generate_json(prompt, 0.3)

            # Process suggestions
            processed_suggestions: List[SuggestionItem] = []
            matched_spans: List[tuple] = []

            for item in data.get("suggestions", []):
                orig = item.get("original_phrase", "").strip()
                if not orig:
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

            rubric_data = data.get("rubric")
            rubric_obj = None
            if rubric_data and isinstance(rubric_data, dict):
                from app.schemas.review import RubricScores
                rubric_obj = RubricScores(
                    grammar=str(rubric_data.get("grammar", "A")),
                    vocabulary=str(rubric_data.get("vocabulary", "B")),
                    naturalness=str(rubric_data.get("naturalness", "A")),
                    clarity=str(rubric_data.get("clarity", "A")),
                    overall_grade=str(rubric_data.get("overall_grade", "A"))
                )

            return ReviewResponse(
                date=date,
                original_text=content,
                corrected_text=data.get("corrected_text", content),
                native_text=data.get("native_text", content),
                overall_feedback=data.get("overall_feedback", "오늘도 멋지게 영어 일기를 작성하셨네요! 꾸준함이 실력 향상의 지름길입니다."),
                followup_question=data.get("followup_question", "What was the most memorable moment of your day?"),
                score=int(data.get("score", 90)),
                rubric=rubric_obj,
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
