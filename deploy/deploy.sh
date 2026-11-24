#!/usr/bin/env bash
# daily-english-diary를 서버(oracle-main)에 배포한다. Mac의 저장소 루트에서 실행:
#   deploy/deploy.sh            테스트 → 빌드 → 전송 → (필요 시 설치) → 재시작 → 상태 확인
#   deploy/deploy.sh --dry-run  보낼 파일만 보여 주고 아무것도 바꾸지 않음
#
# - 커밋된 상태만 배포한다. git 추적 파일 + frontend/dist만 보내고, data/와 .env는 보내지 않는다
#   (data/는 서버가 원본). 서버에서 파일을 지우지 않는다.
# - venv가 없거나 requirements가 바뀌면 설치하고, deploy/*.service가 바뀌면 다시 등록한다.
# - Mac에서는 http://localhost:8020 (com.jinwoo.anki-tunnel 터널)로 연다.
set -euo pipefail

HOST=oracle-main
REMOTE=/home/ubuntu/daily-english-diary
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

cd "$(git rev-parse --show-toplevel)"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "❌ 커밋 안 된 변경이 있습니다. 커밋한 뒤 배포하세요:"; git status --short --untracked-files=no; exit 1
fi
COMMIT=$(git rev-parse --short HEAD)
echo "== 배포 대상 커밋 $COMMIT ($(git log -1 --format=%s))"

echo "== 테스트"
(cd backend && .venv/bin/python -m pytest -q 2>&1 | tail -1)
(cd frontend && npx vitest run 2>&1 | grep -E "Tests ")
echo "== 웹 화면 빌드"
(cd frontend && npm run build >/dev/null)

LIST=$(mktemp)
trap 'rm -f "$LIST"' EXIT
git ls-files | grep -v -E '^data/|(^|/)\.env' > "$LIST"
find frontend/dist -type f >> "$LIST"

if [[ $DRY == 1 ]]; then
  echo "== (dry-run) 바뀔 파일:"
  rsync -azin --files-from="$LIST" ./ "$HOST:$REMOTE/" | grep -v '^\.' || echo "(없음)"
  exit 0
fi

sums() { ssh "$HOST" "cd $REMOTE 2>/dev/null && md5sum $1 2>/dev/null" </dev/null || true; }
REQ_BEFORE=$(sums "backend/requirements.txt gec/requirements.txt")
UNITS_BEFORE=$(sums "deploy/*.service")

echo "== 전송"
rsync -az --files-from="$LIST" ./ "$HOST:$REMOTE/"

if [[ "$REQ_BEFORE" != "$(sums "backend/requirements.txt gec/requirements.txt")" ]] \
   || ! ssh "$HOST" "test -x $REMOTE/backend/.venv/bin/uvicorn -a -x $REMOTE/gec/.venv/bin/python" </dev/null; then
  echo "== 패키지 설치 (처음이면 torch 때문에 몇 분 걸림)"
  ssh "$HOST" "export PATH=\$HOME/.local/bin:\$PATH && cd $REMOTE/backend && { test -d .venv || uv venv -q --python 3.12 .venv; } && uv pip install -q --python .venv/bin/python -r requirements.txt && cd ../gec && { test -x .venv/bin/python && uv pip install -q --python .venv/bin/python -r requirements.txt || bash setup.sh; }" </dev/null
fi

if [[ "$UNITS_BEFORE" != "$(sums "deploy/*.service")" ]]; then
  echo "== 서비스 파일 바뀜 → 등록"
  ssh "$HOST" "cd $REMOTE/deploy && sudo install -m644 *.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable -q diary diary-gec" </dev/null
fi

echo "== 재시작"
ssh "$HOST" "sudo systemctl restart diary-gec diary && echo $COMMIT > $REMOTE/DEPLOYED_COMMIT" </dev/null

echo "== 상태 확인"
ok=0
for i in $(seq 30); do
  if ssh "$HOST" "curl -sf -m5 127.0.0.1:8000/api/health >/dev/null" </dev/null; then ok=1; break; fi
  sleep 2
done
ssh "$HOST" "systemctl is-active diary diary-gec | paste -sd' '; curl -s -m5 127.0.0.1:8010/health || echo 'GECToR 아직 로딩 중(모델 로딩 수십 초)'" </dev/null
if [[ $ok == 1 ]]; then echo "✅ 배포 완료: $COMMIT  → http://localhost:8020"; else echo "❌ 백엔드가 응답하지 않습니다: journalctl -u diary"; exit 1; fi
