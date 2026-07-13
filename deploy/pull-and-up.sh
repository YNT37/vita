#!/usr/bin/env bash
# 在云服务器上：git clone 或 pull 后执行本脚本
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "已生成 backend/.env，请编辑 SECRET_KEY / JWT_SECRET / AI_API_KEY 后重新运行。"
  exit 1
fi

git fetch origin
git checkout main
git pull --ff-only origin main

docker compose up -d --build

echo ""
echo "部署完成。访问 http://$(curl -s ifconfig.me 2>/dev/null || echo '<服务器公网IP>')"
echo "健康检查: curl http://127.0.0.1/api/health"
