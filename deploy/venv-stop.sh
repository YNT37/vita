#!/usr/bin/env bash
# 停止 venv 方式启动的前后端
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/deploy/run"

stop_pidfile() {
  local name="$1"
  local file="$RUN/${name}.pid"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "停止 $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

stop_pidfile backend
stop_pidfile frontend

# 兜底：按端口杀（避免 pid 丢失）
if command -v fuser >/dev/null 2>&1; then
  fuser -k 5000/tcp 2>/dev/null || true
  fuser -k 3000/tcp 2>/dev/null || true
fi

echo "已停止。"
