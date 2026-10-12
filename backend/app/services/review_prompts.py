"""Prompts for the essay review.

The review runs these calls:
- score ([밴드 채점], three times): IELTS bands only;
- main: argument feedback, revision focus, C1+ rewrite, key expressions (no error finding);
- detect ([오류 탐지]): every error, located by sentence number;
- verify ([교정 검증]): accept or reject each candidate in context, group accepted ones into patterns.
Static instructions come first and the essay last, so the shared prefix can be cached.
"""
from typing import List

from app.schemas.review import SuggestionItem

LEARNER = (
    "학습자는 토플 100점 수준(B2~C1)의 한국인입니다. 이 연습의 목적은 형식을 갖춘 글쓰기가 아니라 "
    "**영어 출력**, 즉 자기 생각을 영어로 정확하고 자연스럽게 꺼내는 능력입니다. "
    "서론·결론 유무, 문단 형식, 분량은 감점하지도 지적하지도 않습니다."
)


def numbered_sentences(content: str, spans: List[tuple]) -> str:
    return "\n".join(f"[S{i}] {content[a:b]}" for i, (a, b) in enumerate(spans, start=1))


def build_main_prompt(type_guide: str, prompt_text: str, content: str) -> str:
    return f"""
당신은 IELTS Writing Task 2 채점 경험이 많은 영어 코치입니다. {LEARNER}
피드백의 중심은 언어입니다. 칭찬보다 구체적이고 냉정하게. (문장 단위 오류 교정과 밴드 채점은 다른 단계에서 하므로 여기서는 하지 않습니다.)

[출력 지침]
1. argument (한국어, 각 1~2문장): thesis, strongest_point, weakest_point, missing_counterargument,
   paragraph_comments(문단 번호별 한 줄). 학습자의 예시가 자기 주장과 모순되면 weakest_point에서 그것부터 지적하세요.
2. revision_focus: 고쳐 쓸 때 집중할 표현상의 2~3가지(한국어, 각 한 문장).
3. upgraded_text: 같은 입장·논거로 C1+ 필자가 쓴 버전. 좋은 신문 칼럼처럼 정확하고 담백하게.
   미사여구, 과장된 형용사, IELTS 상투구(foster an environment conducive to, it is undeniable that, plays a pivotal role 등) 금지.
4. key_expressions: upgraded_text에서 다음 글에 바로 쓸 표현 4~6개. expression(someone/something 대신 A, B, V-ing 표기),
   meaning(한국어), pos("n","v","adj","adv","idiom","prep","conj" 중 하나)만 쓰세요.
5. overall_feedback: 한국어 2~3문장(현재 수준, 가장 큰 약점, 다음 한 걸음).

[JSON 응답 규격]
{{
  "argument": {{"thesis": "...", "strongest_point": "...", "weakest_point": "...", "missing_counterargument": "...",
               "paragraph_comments": [{{"paragraph": 1, "comment": "..."}}]}},
  "revision_focus": ["..."],
  "upgraded_text": "...",
  "key_expressions": [{{"expression": "...", "meaning": "...", "pos": "v"}}],
  "overall_feedback": "..."
}}

[에세이 유형]: {type_guide}
[에세이 문제]: {prompt_text}
[학습자 에세이]:
\"\"\"{content}\"\"\"
"""


def build_detect_prompt(prompt_text: str, content: str, spans: List[tuple]) -> str:
    return f"""
[오류 탐지]
당신은 학습자 영어 글의 오류를 찾는 꼼꼼한 영어 교정자입니다. {LEARNER}

[점검 절차] 아래 문장 목록을 [S1]부터 마지막 문장까지 한 문장씩 점검하세요.
문장마다 주어-동사 수일치, 관사(가산명사 단수, 관용적으로 the가 붙는 명사), 동사 형태(to부정사/동명사,
사역·지각동사 구문), 시제, 전치사, 단어 선택과 콜로케이션(한국어 직역)을 확인하고, 발견한 오류는 하나도 빠짐없이 넣습니다.

[규칙]
- sentence: 오류가 있는 문장 번호(정수, [S3]이면 3).
- original_phrase: 그 문장 안에 글자 그대로 있는 2~7단어 구문. 그 문장 안에서 한 번만 나오도록 앞뒤 단어를 붙이세요.
  문장 전체를 바꾸는 제안 금지.
- suggested_phrase: 학습자의 단어를 살린 최소 수정이며, 같은 오류가 남아 있으면 안 됩니다.
- tier: "accuracy" 명백한 오류 / "idiom" 어색한 직역투·부정확한 단어·콜로케이션 / "style" 더 자연스러운 표현(선택).
- 같은 오류가 여러 번 나오면 나올 때마다 각각 만드세요. 축약형 풀기·격식 조정 제안은 하지 마세요.
- category: "Grammar", "Spelling", "Vocabulary", "Natural Expression", "Clarity" 중 하나.
- subcategory: 관사(Article), 수일치(Agreement), 시제(Tense), 전치사(Preposition), 동사 형태(Verb Form),
  단어 선택(Word Choice), 콜로케이션(Collocation), 대명사(Pronoun), 문장 구조(Sentence Structure), 기타 중 하나.
- explanation: 한국어 한 문장.

[JSON 응답 규격]
{{"suggestions": [{{"sentence": 1, "original_phrase": "...", "suggested_phrase": "...", "tier": "accuracy",
                   "category": "Grammar", "subcategory": "관사(Article)", "explanation": "..."}}]}}

[에세이 문제]: {prompt_text}
[문장 목록]
{numbered_sentences(content, spans)}
"""


def build_verify_prompt(prompt_text: str, content: str, spans: List[tuple],
                        candidates: List[SuggestionItem]) -> str:
    sentence_of = {}
    for i, (a, b) in enumerate(spans, start=1):
        for c in candidates:
            if a <= c.start_idx < b:
                sentence_of[c.id] = i
    listing = "\n".join(
        f'{c.id} | S{sentence_of.get(c.id, "?")} | "{c.original_phrase}" → "{c.suggested_phrase}" | {c.tier} | {c.explanation}'
        for c in candidates
    )
    return f"""
[교정 검증]
당신은 엄격한 영어 원어민 편집자입니다. 다른 교정자가 학습자 글에서 찾은 교정 후보를 하나씩 문맥과 함께 판정합니다.
틀린 지적은 학습자가 틀린 규칙을 외우게 만들므로, 확실한 것만 통과시키세요.

[판정 기준]
- valid=true: 원문이 그 문맥에서 문법적으로 틀렸거나(accuracy), 원어민이 쓰지 않는 어색한 표현이고(idiom),
  수정안이 정확하고 의미를 바꾸지 않을 때. style 후보는 수정안이 분명히 더 자연스러울 때만 true.
- valid=false: 원문이 그 문맥에서 이미 문법적으로 맞고 자연스러운 경우(불가산으로 쓰인 명사, 관용적으로 관사 없이 쓰는 표현 포함),
  수정안에 새 오류가 있거나 의미가 바뀌는 경우, 단순한 취향 차이인 경우.
- 판정할 때는 해당 문장뿐 아니라 앞뒤 문장도 보세요.

[패턴 묶기]
valid=true인 후보 중 같은 구체적 오류(같은 단어, 같은 구조)가 2번 이상이면 patterns로 묶으세요(최대 4개, 많은 순, 없으면 []).
'관사 오류', '직역투' 같은 넓은 범주가 아니라 구체적인 단어·구조 단위로 묶으세요.
pattern(한국어 이름), ids(후보 id 목록), fix(영어), tip(한국어 한 문장).

[JSON 응답 규격]
{{"verdicts": [{{"id": "c1", "valid": true, "reason": "한국어 짧게"}}],
  "patterns": [{{"pattern": "...", "ids": ["c1", "c2"], "fix": "...", "tip": "..."}}]}}

[에세이 문제]: {prompt_text}
[문장 목록]
{numbered_sentences(content, spans)}

[교정 후보]
{listing}
"""


def build_score_prompt(type_guide: str, prompt_text: str, content: str) -> str:
    return f"""
[밴드 채점]
당신은 IELTS Writing Task 2 공인 채점관입니다. {LEARNER}
아래 기준표에 맞춰 4개 기준을 각각 0~9 밴드(0.5 단위)로 채점하세요. 먼저 기준표의 어느 칸에 가장 가까운지 판단한 뒤 숫자를 정하세요.
분량·서론·결론 형식은 점수에 반영하지 않습니다.

[기준표]
- task_response (질문에 답하고 입장과 근거를 전달하는가)
  밴드 5: 입장이 불분명하거나 근거가 부족·반복적 / 밴드 6: 입장은 있으나 근거 전개가 얕거나 일반론 / 밴드 7: 입장이 분명하고 근거를 구체적으로 전개 / 밴드 8: 모든 부분에 충분히 답하고 근거가 잘 뒷받침됨
- coherence (문장과 아이디어의 연결, 연결어 사용)
  밴드 5: 전개가 끊기고 연결어가 부족하거나 기계적 / 밴드 6: 대체로 이어지나 연결어 남용·오용, 문단 내 흐름이 고르지 않음 / 밴드 7: 논리적으로 이어지고 연결어를 적절히 사용 / 밴드 8: 흐름이 매끄럽고 연결이 자연스러움
- lexical (어휘의 정확성·폭·콜로케이션)
  밴드 5: 어휘가 제한적이고 의미를 흐리는 오류가 잦음 / 밴드 6: 과제에 충분한 어휘, 단어 선택·콜로케이션 오류가 있으나 의미는 통함 / 밴드 7: 덜 흔한 어휘와 콜로케이션을 쓰고 오류가 가끔 있음 / 밴드 8: 폭넓고 정확하며 오류가 드묾
- grammar (문법 정확성과 구조의 다양성)
  밴드 5: 구조가 단순하고 오류가 잦아 이해를 방해 / 밴드 6: 단순·복합 구조를 섞지만 오류(관사, 수일치, 시제 등)가 자주 보임 / 밴드 7: 다양한 복합 구조, 오류 없는 문장이 많고 오류가 가끔 있음 / 밴드 8: 대부분의 문장에 오류가 없음

[출력] 기준마다 band(숫자)와 comment(한국어 한 줄, 그 점수의 핵심 근거).

[JSON 응답 규격]
{{"task_response": {{"band": <0~9, 0.5 단위>, "comment": "..."}},
  "coherence": {{"band": <0~9, 0.5 단위>, "comment": "..."}},
  "lexical": {{"band": <0~9, 0.5 단위>, "comment": "..."}},
  "grammar": {{"band": <0~9, 0.5 단위>, "comment": "..."}}}}

[에세이 유형]: {type_guide}
[에세이 문제]: {prompt_text}
[학습자 에세이]:
\"\"\"{content}\"\"\"
"""
