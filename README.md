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
Next.js 16(App Router+TS+Tailwind v4) · Flask + SQLAlchemy · PostgreSQL · LangChain + OpenAI 兼容 / Anthropic · JWT

## 📁 结构
```
vita/
├── backend/     # Flask + SQLAlchemy（本地 SQLite，线上 PostgreSQL）
├── frontend/    # Next.js
└── docs/        # 需求 / 架构 / API / prompt_log / 研发日志 / 审查清单
```

## 🗺️ 前端路由（当前进度）
| 路由 | 页面 | 状态 |
|---|---|---|
| `/login` | 登录 | ✅ |
| `/register` | 注册 | ✅ |
| `/` | **AI 管家（主页）** | ✅ |
| `/stats` | 统计中心（概览/资产/待办/分类） | ✅ |
| `/records` | 记账 | ✅ |
| `/reminders` | 提醒 | ✅ |
| `/user` | **我的**（账号 / 摘要 / 退出） | ✅ |
| `/settings` | AI 设置（性格 / API Key，从「我的」进入） | ✅ |
| `/persona` | 重定向至 `/` | ✅ |

底栏：管家 · 统计 · 记账 · 提醒 · 我的（手机）；桌面端为左侧导航栏。页面自适应手机与电脑浏览器。

## 🚀 本地运行

### 后端（Flask · 端口 5000 · 推荐 venv）
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env    # 本地 SQLite 可留空 DATABASE_URL
python app.py                  # http://localhost:5000/api/health
```

Linux / macOS：
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### 前端（Next.js · 端口 3000）
```powershell
cd frontend
Copy-Item .env.local.example .env.local -ErrorAction SilentlyContinue
# 若无 example：新建 .env.local，内容 NEXT_PUBLIC_API_BASE=http://localhost:5000
npm install    # 首次
npm run dev    # http://localhost:3000
```

> 前后端需**同时运行**。注册/登录后可在浏览器操作记账与提醒。

## 🔑 环境变量（摘要）

完整逐项说明 → [docs/部署教程.md](docs/部署教程.md) 第 2～3 节。

| 变量 | 位置 | 说明 |
|---|---|---|
| `SECRET_KEY` / `JWT_SECRET` | `backend/.env` | 上线必改随机串 |
| `DATABASE_URL` | `backend/.env` | 留空→SQLite；Postgres 填连接串 |
| `AI_*` | `backend/.env` | 可选，也可网页设置 |
| `PUBLIC_HOST` | `deploy/.env` | 云服务器 venv：公网 IP |
| `NEXT_PUBLIC_API_BASE` | `frontend/.env.local` | 本机开发指向后端 |

### 微信提醒（Server酱）绑定步骤
1. 打开 https://sct.ftqq.com ，用**微信扫码登录**（无需下载 App）
2. 在「Key&API」复制 **SendKey**
3. 登录 Vita → **我的** → 粘贴 SendKey → 保存 → **发送测试**
4. 创建已到期的提醒，点「立即检查到期」或等待后台扫描

### 浏览器弹窗提醒（推荐）
1. 登录 Vita → **我的** → **开启浏览器通知**
2. 浏览器弹出权限框时点「允许」
3. 点「发送测试弹窗」验证；到期待办约每 45 秒检查一次（需保持网页打开）

## 📦 部署

**完整教程（环境变量逐项说明 + 数据库安装 + 5 种上线方式）→ [docs/部署教程.md](docs/部署教程.md)**

| 方式 | 一句话 |
|------|--------|
| A 本机 venv + SQLite | 开发默认 |
| B 云服务器 venv + SQLite | 最快演示 |
| C 云服务器 venv + PostgreSQL | 更稳 |
| D Docker Compose + SQLite | 一键 `:80` |
| E Docker Compose + PostgreSQL | 容器化正式 |

### 云服务器快速开始（方式 B）

```bash
git clone https://github.com/YNT37/vita.git && cd vita
cp deploy/.env.example deploy/.env && vim deploy/.env          # PUBLIC_HOST=公网IP
cp backend/.env.example backend/.env && vim backend/.env      # SECRET_KEY / JWT_SECRET
chmod +x deploy/*.sh && ./deploy/venv-setup.sh && ./deploy/venv-start.sh
```

细节、Postgres 建库、Docker 命令见部署教程，勿只改 `.env.example` 注释。

## 🌐 线上地址
- 方式 B/C：`http://<公网IP>:3000`（API `:5000`）
- 方式 D/E：`http://<公网IP>/`

## 📚 文档
| 文档 | 说明 |
|---|---|
| [docs/部署教程.md](docs/部署教程.md) | **部署与数据库完整指南** |
| [docs/需求文档.md](docs/需求文档.md) | 功能需求 FRD v1.1 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计 |
| [docs/API文档.md](docs/API文档.md) | 接口契约 |
| [docs/prompt_log.md](docs/prompt_log.md) | AI Prompt 日志（考核 10%） |
| [docs/研发日志/](docs/研发日志/) | 每日研发总结 |
| [docs/review_checklist.md](docs/review_checklist.md) | 代码审查清单 |

## 🔀 分支说明
- `main`：当前主干（前后端完整）
- `feat/persona-frontend`：已合并进 `main` 的开发支线
