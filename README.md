# Vita · AI 生活管家

> 一个会「说话」的多用户生活管家。用户注册登录后，选择一个 AI 角色（管家 / 奴才 / 毒舌闺蜜 / 暖心恋人），
> 它用对应语气帮你记账、管日程提醒，并提供情绪价值。

《移动应用项目工程实践》居家实训考核作品。

**仓库**：https://github.com/YNT37/vita

## ✨ 功能
- 🔐 多用户账号体系（注册/登录，JWT 鉴权，数据按用户隔离）✅
- 💰 记账理财：记一笔 / 分类 / 收支统计 ✅
- ⏰ 日程提醒：待办 / 账单；**浏览器弹窗提醒**（推荐）+ 可选 Server酱 微信推送 ✅
- 🤖 AI 管家：角色切换 + 对话 + 每日简报 + 自然语言确认卡 ✅

## 🧱 技术栈
Next.js 16(App Router+TS+Tailwind v4) · Flask + SQLAlchemy · SQLite / PostgreSQL · LangChain + OpenAI 兼容 / Anthropic · JWT · Docker

## 📁 结构
```
vita/
├── backend/              # Flask
├── frontend/             # Next.js
├── deploy/               # Caddyfile、pull-and-up.sh
├── docker-compose.yml    # 默认部署（SQLite）
├── docker-compose.postgres.yml
└── docs/                 # 需求 / 架构 / API / 部署 / prompt_log
```

## 🗺️ 前端路由
| 路由 | 页面 | 状态 |
|---|---|---|
| `/login` | 登录 | ✅ |
| `/register` | 注册 | ✅ |
| `/` | **AI 管家（主页）** | ✅ |
| `/stats` | 统计中心 | ✅ |
| `/records` | 记账 | ✅ |
| `/reminders` | 提醒 | ✅ |
| `/user` | **我的** | ✅ |
| `/settings` | AI 设置 | ✅ |
| `/persona` | 重定向至 `/` | ✅ |

## 🚀 本地运行（开发热重载）

写代码用 venv + `npm run dev`。只想本机跑通产品 → [本地 Docker](docs/部署/本地-Docker.md)。

### 后端
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env && python app.py
```

### 前端
```powershell
cd frontend
# .env.local 内容：NEXT_PUBLIC_API_BASE=http://localhost:5000
npm install
npm run dev
```

## 🔑 环境变量（摘要）

Docker 部署详解 → [docs/部署/环境变量.md](docs/部署/环境变量.md)

| 变量 | 位置 | 说明 |
|---|---|---|
| `SECRET_KEY` / `JWT_SECRET` | `backend/.env` | 上线必改 |
| `DATABASE_URL` | `backend/.env` | Docker+SQLite 可留空；Postgres 用 `@db:5432` |
| `AI_*` | `backend/.env` | 可选 |
| `NEXT_PUBLIC_API_BASE` | 仅本机 `npm run dev` | Docker 同域反代时构建为空 |

### 微信提醒（Server酱）
1. https://sct.ftqq.com 微信扫码 → 复制 SendKey  
2. Vita「我的」粘贴 → 保存 → 发送测试  

### 浏览器弹窗提醒（推荐）
「我的」→ 开启浏览器通知 → 允许 → 发送测试（页面保持打开）。

## 📦 部署（统一 Docker）

**→ [docs/部署/README.md](docs/部署/README.md)**

| 方式 | 文档 | 访问 |
|------|------|------|
| 本地 | [本地-Docker.md](docs/部署/本地-Docker.md) | `http://localhost` |
| 云服务器 | [云服务器-Docker.md](docs/部署/云服务器-Docker.md) | `http://公网IP/` |

云服务器最快路径：

```bash
git clone https://github.com/YNT37/vita.git && cd vita
cp backend/.env.example backend/.env && vim backend/.env   # SECRET_KEY / JWT_SECRET
docker compose up -d --build
# 之后更新：chmod +x deploy/pull-and-up.sh && ./deploy/pull-and-up.sh
```

默认 SQLite；可选 Postgres 见部署文档。

## 🌐 线上地址
- **https://vita.sanseven.top/**（生产 · HTTPS · Let's Encrypt）
- 备用 IP：`http://60.204.132.56/`（证书绑定域名，请优先用域名）

## 📚 文档
| 文档 | 说明 |
|---|---|
| [docs/资料索引.md](docs/资料索引.md) | **交付材料总目录** |
| [docs/演示大纲.md](docs/演示大纲.md) | **录屏 / 演示脚本** |
| [docs/部署/README.md](docs/部署/README.md) | 部署（本地 / 云 · Docker） |
| [docs/需求文档.md](docs/需求文档.md) | 功能需求 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构 |
| [docs/API文档.md](docs/API文档.md) | 接口 |
| [docs/prompt_log.md](docs/prompt_log.md) | Prompt 日志 |
| [docs/研发日志/](docs/研发日志/) | 研发日志 |
| [docs/review_checklist.md](docs/review_checklist.md) | 审查清单 |

## 🔀 分支
- `main`：主干
