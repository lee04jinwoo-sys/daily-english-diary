# ✍️ Daily English Diary (AI 일기 관리 & 실시간 Grammarly 첨삭 & Anki 연동)

매일 영어 일기를 작성하고, **Gemini 2.5 Flash**를 활용하여 **Grammarly 스타일의 실시간 인라인 첨삭(문법 교정, 원어민 자연스러운 패러프레이징, 원클릭 적용)**을 받으며, **Shadowing Player 호환 Anki 플래시카드(문장/단어)**로 즉시 내보내어 복습할 수 있는 노션/애플 메모 감성의 모던 웹 애플리케이션입니다.

---

## ✨ 핵심 기능

1. **노션 / 애플 메모 스타일의 집중형 에디터**:
   - 눈이 편안한 페이퍼 감성 미니멀 디자인
   - 초단위 실시간 자동 임시 저장 (Draft Auto-save)으로 글 유실 방지
2. **Grammarly 스타일 인라인 첨삭 & 원클릭 적용**:
   - 🔴 문법 오류 (Grammar), 🟠 철자 (Spelling), 🟡 전달력 (Clarity), 🔵 원어민 표현 (Natural Expression), 🟢 어휘 (Vocabulary) 인라인 하이라이트
   - 우측 사이드 패널의 교정 카드에서 **[적용 (Accept)]** 클릭 시 본문 텍스트 즉시 치환 및 하이라이트 자동 재정렬
   - 4개 탭 비교: `작성 & 첨삭 모드` | `원어민 패러프레이징` | `문법 교정본` | `나란히 비교 (Diff)`
   - AI 튜터의 일기 내용 공감 코멘트 및 영어 후속 질문 (Follow-up Question)
3. **Shadowing Player 호환 Anki 연동 (카드 미리보기 모달)**:
   - 교정 카드 및 본문 추출 표현마다 **[Anki 문장/단어 카드에 추가]** 버튼 제공
   - 카드 등록 전 팝업 모달에서 앞면/뒷면/해설/덱 확인 및 수정 지원
   - `gTTS` 원어민 오디오 파일 자동 생성 및 Anki 미디어 저장 (`[sound:...]` 태그 자동 생성)
   - `English Sentence` 덱 (`1. Language::1.1. English::Sentence`) 및 `English Vocabulary` 덱 (`1. Language::1.1. English::Vocabulary`) 완벽 호환
   - Anki 실행 상태 감지 및 원클릭 앱 실행(`open -a Anki`)
4. **캘린더 & 스트릭 (Streak) 일기 관리**:
   - 달력 뷰에서 날짜별 작성 현황(작성 여부, 단어 수, 점수) 한눈에 확인
   - 연속 작성 스트릭(Streak) 추적 및 축하 애니메이션 (Confetti)
5. **학습 분석 통계 대시보드 (Analytics)**:
   - 자주 틀리는 문법 유형(시제, 전치사, 수일치, 관사 등) 발생 빈도 시각화
   - 실수 패턴별 원문 vs 추천 예문 모음 및 Anki 카드 저장

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
- 웹 UI: `http://localhost:5173`

---

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python 3.11+, FastAPI (Lifespan), Pydantic v2, Google GenAI SDK (`google-genai`), `aiosqlite`, `gTTS`, `requests`, `python-dotenv`
- **Frontend**: React 19, TypeScript (Strict), Vite, Tailwind CSS, Lucide React, Canvas Confetti
- **Database**: SQLite (`data/diary.db`)
- **Integration**: AnkiConnect (`http://localhost:8765`)
