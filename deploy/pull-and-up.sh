#!/usr/bin/env bash
# 从 GitHub 拉取 main，并用 Docker Compose 重新部署（默认 SQLite 版）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "已生成 backend/.env，请 vim 修改 SECRET_KEY / JWT_SECRET 后重新运行。"
  exit 1
fi

git fetch origin
git checkout main
git pull --ff-only origin main

docker compose up -d --build

echo ""
echo "部署完成。访问 http://$(curl -s ifconfig.me 2>/dev/null || echo '<公网IP>')/"
echo "健康检查: curl -s http://127.0.0.1/api/health"
echo "若使用 Postgres 编排，请改用 docs/部署/云服务器-Docker.md 中的命令。"
