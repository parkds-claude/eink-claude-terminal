#!/bin/zsh
# X4 TourBox 키맵 표시 기동 스크립트 (표준 진입점)
# launchd 에이전트(com.x4mirror.bridge)가 있으면 재기동 위임, 없으면 직접 기동.
# 사용: scripts/start_tourbox_display.sh [X4_IP]

set -euo pipefail

X4_IP="${1:-x4-terminal.local}"
BRIDGE="$HOME/eink-claude-terminal/bridge/x4_tourbox_display.py"
LOG="$HOME/eink-claude-terminal/bridge.log"
PIDFILE="$HOME/eink-claude-terminal/bridge.pid"

if launchctl print "gui/$(id -u)/com.x4mirror.bridge" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/com.x4mirror.bridge"
  echo "launchd 에이전트(com.x4mirror.bridge) 재기동으로 위임했습니다."
  exit 0
fi

if ! curl -s -m 3 "http://$X4_IP/status" | grep -q '"ok":true'; then
  echo "ERROR: X4($X4_IP) /status 응답 없음" >&2
  exit 1
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  sleep 1
fi
TOKEN=$(cat "$HOME/eink-claude-terminal/.x4-token" 2>/dev/null || echo "")
nohup python3 "$BRIDGE" --x4 "http://$X4_IP" --token "$TOKEN" >>"$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "TourBox 표시 기동: PID $(cat "$PIDFILE") → http://$X4_IP (로그: $LOG)"
