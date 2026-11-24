#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "      ✍️ Daily English Essay (AI 첨삭 & Anki)      "
echo "=================================================="

# Kill any existing processes on ports 8000 and 5173
lsof -ti :8000 | xargs kill -9 2>/dev/null
lsof -ti :5173 | xargs kill -9 2>/dev/null

# Activate Python Virtualenv and start Backend
echo "🚀 1. 백엔드(FastAPI) 서버 구동 중... (http://localhost:8000)"
cd "$DIR/backend"
"$DIR/backend/.venv/bin/python" run.py &
BACKEND_PID=$!

# Second error detector (GECToR). Optional: set up once with gec/setup.sh; without it reviews run as before.
GEC_PID=""
if [ -x "$DIR/gec/.venv/bin/python" ]; then
    lsof -ti :8010 | xargs kill -9 2>/dev/null
    echo "🔎 GECToR 문법 탐지 서버 구동 중... (http://127.0.0.1:8010)"
    "$DIR/gec/.venv/bin/python" "$DIR/gec/server.py" &
    GEC_PID=$!
fi

# Start Frontend
echo "✨ 2. 프론트엔드(Vite React) 개발 서버 구동 중... (http://localhost:5173)"
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

sleep 2
echo "🌐 브라우저를 엽니다: http://localhost:5173"
open "http://localhost:5173"

cleanup() {
    echo ""
    echo "🛑 Daily English Essay 서버를 종료합니다..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    [ -n "$GEC_PID" ] && kill $GEC_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

wait
