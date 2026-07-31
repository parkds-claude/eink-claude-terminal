#!/bin/zsh
# launchd용 미러 데몬 (포그라운드 실행 — KeepAlive가 크래시 시 재기동)
# launchd의 좁은 PATH 대비 homebrew 경로 명시 (CLAUDE.md gotcha)
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

X4_URL="${X4_URL:-http://x4-terminal.local}"
SESSION="x4-terminal"
FONT_SIZE="${FONT_SIZE:-22}"
BRIDGE="$HOME/eink-claude-terminal/bridge/x4_bitmap_bridge.py"
PIDFILE="$HOME/eink-claude-terminal/bridge.pid"
TOKEN=$(cat "$HOME/eink-claude-terminal/.x4-token" 2>/dev/null || echo "")

# tmux 세션 보장 (부팅 직후에는 tmux 서버 자체가 없을 수 있음)
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -x 72 -y 19
fi

# 수동 기동된 구 브리지가 있으면 정리
if [[ -f "$PIDFILE" ]]; then
  OLD=$(cat "$PIDFILE")
  [[ "$OLD" != "$$" ]] && kill "$OLD" 2>/dev/null || true
fi
echo $$ > "$PIDFILE"

exec python3 "$BRIDGE" --x4 "$X4_URL" --target "$SESSION:" \
  --font-size "$FONT_SIZE" --interval 0.12 --token "$TOKEN"
