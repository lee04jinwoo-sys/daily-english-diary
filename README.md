# ✍️ Daily English Essay (논증 에세이 연습 · AI 첨삭 · Anki 연동)

B2~C1 학습자를 위한 영어 **논증 에세이** 연습 앱입니다. 원래 일기 앱이었으나 2026-10-10에 에세이 중심으로 바꿨습니다(폴더·저장소 이름은 그대로).

## ✨ 핵심 기능

1. **주제 은행 (120개) + 자유 주제**
   - 유형 5가지: 찬반 / 양쪽 견해 / 장단점 / 원인·해결 / 가정. 유형마다 훈련되는 구조(양보-반박, 인과, 가정법 등)가 다릅니다.
   - 분야 비율 일반 50% · 내 분야(투자·퀀트·AI·커리어) 30% · 시사 20%로 추천합니다.
   - 아직 쓰지 않은 주제만, 직전 에세이와 다른 유형으로 추천합니다. `backend/app/data/topics.json`
   - 원하면 내 질문으로 바로 시작할 수 있습니다. 시간 제한·분량 제한은 없습니다.
2. **AI 첨삭 (Gemini)**
   - IELTS Task 2의 4대 기준(과제 수행 / 구성·흐름 / 어휘 / 문법) 밴드 추정과 기준별 코멘트
   - 논증 피드백: 입장, 가장 강한 부분, 가장 약한 논거와 보강법, 다뤄야 할 반론, 문단별 코멘트
   - 고쳐 쓸 때 집중할 2~3가지 + **같은 주제로 고쳐 쓰기**(이전 밴드와 비교)
   - 인라인 교정(필수 교정 / 원어민 표현 / 스타일, 구문 단위 최소 수정) 원클릭 적용
   - 같은 논지의 C1+ 업그레이드 버전, 문장별 대조
3. **Anki 연동**: 교정 문장·핵심 표현을 `English Sentence` / `English Vocabulary` 덱에 추가합니다. 이 앱은 Anki 카드를 **삭제하지 않습니다**.
4. **통계**: 에세이별 밴드 추이(기준별), 유형별 평균 밴드, 100단어당 교정 밀도, 작성 히트맵과 스트릭

> AI 채점은 같은 글에도 0.5 밴드 정도 흔들립니다. 한 편의 점수보다 여러 편의 추세를 보세요.

---

## 🚀 빠른 시작 (Quick Start)

### 1) 원클릭 실행 스크립트
터미널에서 아래 명령을 실행하거나, Finder에서 `DailyEnglishDiary.command`를 더블클릭합니다:
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
- 테스트는 임시 DB를 쓰며 `data/diary.db`를 건드리지 않습니다.

---

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python 3.11+, FastAPI (Lifespan), Pydantic v2, Google GenAI SDK (`google-genai`), `aiosqlite`, `gTTS`, `requests`, `python-dotenv`
- **Frontend**: React 19, TypeScript (Strict), Vite, Tailwind CSS, Lucide React, Canvas Confetti
- **Database**: SQLite (`data/diary.db`, `essays` / `essay_suggestions` 테이블. 예전 `diaries` 테이블은 건드리지 않고 남겨둠). `ESSAY_DB_PATH`로 경로 변경 가능
- **Integration**: AnkiConnect (`http://localhost:8765`)
