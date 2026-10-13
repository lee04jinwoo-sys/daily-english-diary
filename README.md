# ✍️ Daily English Essay (논증 에세이 연습 · AI 첨삭 · Anki 연동)

B2~C1 학습자를 위한 영어 **논증 에세이** 연습 앱입니다. 원래 일기 앱이었으나 2026-10-10에 에세이 중심으로 바꿨습니다(폴더·저장소 이름은 그대로).

## ✨ 핵심 기능

1. **IELTS Task 2 기출 주제 은행 (1,946개) + 자유 주제**
   - 출처: Hugging Face 데이터셋 [`btnotpt/ielts_task_2`](https://huggingface.co/datasets/btnotpt/ielts_task_2) (Apache-2.0)의 수험자 입력 주제. `backend/scripts/build_ielts_topics.py`로 정제합니다: Task 1·TOEFL 문항·깨진 인코딩·잘린 문장 제거 → 같은 질문의 변형 병합(가장 많이 쓰인 문구 유지) → Gemini가 Task 2 여부 판정·유형/테마 분류·철자/문법만 수정(원문 대비 15% 넘게 바뀌면 버림). 결과: `backend/app/data/ielts_topics.json`
   - 유형 5가지: 찬반 / 양쪽 견해 / 장단점 / 원인·해결 / 두 질문. 원본은 찬반형이 43%라서 **유형을 고르게** 뽑습니다.
   - 아직 쓰지 않은 주제만, 직전 에세이와 다른 유형 · 다른 테마로 추천합니다. 주제 카드에 데이터셋에서 그 주제로 쓴 수험자 수를 표시합니다.
   - 원하면 내 질문으로 바로 시작할 수 있습니다. 시간 제한·분량 제한은 없습니다.
   - **쓰기 타이머**: 타자를 치는 동안만 잽니다. 2분 동안 입력이 없으면 멈추고, 다시 치면 이어서 잽니다(`frontend/src/hooks/useWritingTimer.ts`의 `IDLE_LIMIT_MS`).
2. **AI 첨삭 (Gemini)** — 목적은 형식적인 글쓰기가 아니라 **영어 출력**입니다. 서론·결론·문단 형식·분량은 감점하지 않습니다.
   - **반복 패턴**: 같은 오류나 한국어 직역 습관을 묶어 횟수·예문·고친 형태·팁으로 보여주고, 패턴마다 Anki 카드를 만들 수 있습니다
   - IELTS Task 2의 4대 기준(과제 수행 / 구성·흐름 / 어휘 / 문법) 밴드 추정과 기준별 코멘트
   - 논증 피드백: 입장, 가장 강한 부분, 가장 약한 논거와 보강법, 다뤄야 할 반론, 문단별 코멘트
   - 고쳐 쓸 때 집중할 2~3가지 + **같은 주제로 고쳐 쓰기**(이전 밴드와 비교)
   - 인라인 교정(필수 교정 / 원어민 표현 / 스타일, 구문 단위 최소 수정). 원문에 자동 적용하지 않고 교정 기록으로 남깁니다(직접 고쳐 쓰기)
   - 같은 논지의 C1+ 업그레이드 버전, 문장별 대조
3. **Anki 연동**: 교정 문장·핵심 표현을 `English Sentence` / `English Vocabulary` 덱에 추가합니다. 문법 교정(교정 카드와 반복 패턴)은 `English Grammar` 객관식 카드로도 만들 수 있습니다: 교정된 문장에서 고친 부분이 빈칸이 되고, **내가 실제로 쓴 틀린 형태가 오답 보기**로 들어갑니다. 해설·설명·나머지 오답 2개는 Anki Manager 게이트웨이(`/api/cards/grammar`)가 채웁니다. 이 앱은 Anki 카드를 **삭제하지 않습니다**.
4. **통계**: 에세이별 밴드 추이(기준별), 유형별 평균 밴드, 100단어당 교정 밀도, 작성 히트맵과 스트릭

> AI 채점은 같은 글에도 0.5 밴드 정도 흔들립니다. 한 편의 점수보다 여러 편의 추세를 보세요.

---

## 🚀 빠른 시작 (Quick Start)

### 1) 원클릭 실행 스크립트
터미널에서 아래 명령을 실행하거나, Finder에서 `DailyEnglishEssay.command`를 더블클릭합니다:
```bash
cd ~/Desktop/Projects/daily-english-diary
./start.sh
```
- 백엔드(FastAPI)와 프론트엔드(Vite React)가 동시에 구동되고 브라우저(`http://localhost:5173`)가 자동으로 열립니다.

### 2) 수동 실행 방법

**백엔드 실행**:
```bash
cd backend
source .venv/bin/activate
python run.py
```
- FastAPI 서버: `http://localhost:8000` (API Docs: `http://localhost:8000/docs`)

**프론트엔드 실행**:
```bash
cd frontend
npm run dev
```
- 웹 UI: `http://localhost:5173` (`API_TARGET` 환경변수로 백엔드 주소 변경 가능)

**테스트**:
```bash
cd backend
.venv/bin/python -m pytest -q
```
- 테스트는 임시 DB를 쓰며 `data/essay.db`를 건드리지 않습니다.

---

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python 3.11+, FastAPI (Lifespan), Pydantic v2, Google GenAI SDK (`google-genai`), `aiosqlite`, `gTTS`, `requests`, `python-dotenv`
- **Frontend**: React 19, TypeScript (Strict), Vite, Tailwind CSS, Lucide React, Canvas Confetti
- **Database**: SQLite (`data/essay.db` — 예전 `diary.db`는 시작 시 자동으로 이름이 바뀜, `essays` / `essay_suggestions` 테이블. 예전 `diaries` 테이블은 건드리지 않고 남겨둠). `ESSAY_DB_PATH`로 경로 변경 가능
- **Integration**: AnkiConnect (`http://localhost:8765`)
