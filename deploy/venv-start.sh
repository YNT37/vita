#!/usr/bin/env bash
# 用 venv + Next 生产模式启动（后台）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f deploy/.env ]]; then
  echo "缺少 deploy/.env，请先: cp deploy/.env.example deploy/.env"
  exit 1
fi
# shellcheck disable=SC1091
source deploy/.env

PUBLIC_HOST="${PUBLIC_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
VENV="${VENV_DIR:-$ROOT/backend/.venv}"
API_BASE="http://${PUBLIC_HOST}:${BACKEND_PORT}"

if [[ ! -x "$VENV/bin/gunicorn" ]]; then
  echo "未找到 $VENV，请先运行: ./deploy/venv-setup.sh"
  exit 1
fi
if [[ ! -f backend/.env ]]; then
  echo "缺少 backend/.env"
  exit 1
fi

mkdir -p deploy/run
./deploy/venv-stop.sh 2>/dev/null || true

echo ">>> 构建前端 NEXT_PUBLIC_API_BASE=$API_BASE"
cd frontend
export NEXT_PUBLIC_API_BASE="$API_BASE"
npm run build
cd "$ROOT"

echo ">>> 启动后端 gunicorn :$BACKEND_PORT"
cd backend
# 加载 .env 由 dotenv / config 完成；工作目录需在 backend
nohup "$VENV/bin/gunicorn" -b "0.0.0.0:${BACKEND_PORT}" -w 1 --timeout 120 app:app \
  > "$ROOT/deploy/run/backend.log" 2>&1 &
echo $! > "$ROOT/deploy/run/backend.pid"
cd "$ROOT"

echo ">>> 启动前端 next start :$FRONTEND_PORT"
cd frontend
nohup npm run start -- -p "$FRONTEND_PORT" -H 0.0.0.0 \
  > "$ROOT/deploy/run/frontend.log" 2>&1 &
echo $! > "$ROOT/deploy/run/frontend.pid"
cd "$ROOT"

sleep 2
echo ""
echo "已启动。"
echo "  前端: http://${PUBLIC_HOST}:${FRONTEND_PORT}"
echo "  后端: http://${PUBLIC_HOST}:${BACKEND_PORT}"
echo "  健康: curl http://127.0.0.1:${BACKEND_PORT}/api/health"
echo "  日志: deploy/run/backend.log  deploy/run/frontend.log"
echo "  停止: ./deploy/venv-stop.sh"
