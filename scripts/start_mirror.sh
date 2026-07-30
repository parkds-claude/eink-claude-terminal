#!/bin/zsh
# X4 e-ink 터미널 미러 기동 스크립트 (표준 진입점)
# - tmux 세션 'x4-terminal'(66x29)이 없으면 생성
# - xteink-terminal 브리지를 백그라운드로 기동 (이미 돌고 있으면 재기동)
# 사용: scripts/start_mirror.sh [X4_IP]

set -euo pipefail

X4_IP="${1:-192.168.0.5}"
SESSION="x4-terminal"
COLS=66
ROWS=29
BRIDGE="$HOME/xteink-terminal/mac-bridge/x4_tmux_bridge.py"
LOG="$HOME/eink-claude-terminal/bridge.log"
PIDFILE="$HOME/eink-claude-terminal/bridge.pid"

# 1) X4 응답 확인
if ! curl -s -m 3 "http://$X4_IP/status" | grep -q '"ok":true'; then
  echo "ERROR: X4($X4_IP) /status 응답 없음" >&2
  exit 1
fi

# 2) tmux 세션 준비
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -x "$COLS" -y "$ROWS"
  echo "tmux 세션 '$SESSION' 생성 (${COLS}x${ROWS})"
fi

# 3) 기존 브리지 정리 후 기동
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  sleep 1
fi
nohup python3 "$BRIDGE" --x4 "http://$X4_IP" --target "$SESSION:" \
  --cols "$COLS" --rows "$ROWS" --interval 0.25 >>"$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "브리지 기동: PID $(cat "$PIDFILE") → http://$X4_IP (로그: $LOG)"
echo "타이핑: 아무 터미널에서 'tmux attach -t $SESSION'"
