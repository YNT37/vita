#!/usr/bin/env bash
# 从 GitHub 拉取最新 main，并用 venv 方式重新部署
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git fetch origin
git checkout main
git pull --ff-only origin main

chmod +x deploy/venv-setup.sh deploy/venv-start.sh deploy/venv-stop.sh deploy/pull-and-up.sh

./deploy/venv-setup.sh
./deploy/venv-start.sh
