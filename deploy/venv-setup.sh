#!/usr/bin/env bash
# 首次或依赖变更时：创建/更新 backend venv + 安装前端依赖
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f deploy/.env ]]; then
  cp deploy/.env.example deploy/.env
  echo "已生成 deploy/.env，请填写 PUBLIC_HOST（公网 IP）后重新运行。"
  exit 1
fi
# shellcheck disable=SC1091
source deploy/.env

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "已生成 backend/.env，请至少修改 SECRET_KEY / JWT_SECRET（可选填 AI_API_KEY）。"
  echo "改完后重新执行: ./deploy/venv-setup.sh"
  exit 1
fi

VENV="${VENV_DIR:-$ROOT/backend/.venv}"
PYTHON="${PYTHON:-python3}"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo ">>> 创建虚拟环境: $VENV"
  "$PYTHON" -m venv "$VENV"
fi

echo ">>> pip install (backend)"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install -r backend/requirements.txt

echo ">>> npm install (frontend)"
cd frontend
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
cd "$ROOT"

mkdir -p deploy/run
echo "依赖就绪。"
echo "  启动: ./deploy/venv-start.sh"
echo "  停止: ./deploy/venv-stop.sh"
