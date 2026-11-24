#!/bin/bash
# diary runs on the server (deploy/deploy.sh); the Mac opens it through the com.jinwoo.anki-tunnel SSH tunnel.
# Local development: ./start.sh (uses the Mac's own data/, which is no longer the original).
if curl -sf -m5 http://localhost:8020/api/health >/dev/null; then
  open "http://localhost:8020"
else
  echo "서버 diary에 연결할 수 없습니다. 터널 확인: launchctl kickstart -k gui/$(id -u)/com.jinwoo.anki-tunnel"
  read -n1 -p "아무 키나 누르면 닫힙니다"
fi
