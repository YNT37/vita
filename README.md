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

### 后端（Flask · 端口 5000）
```powershell
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env    # 本地 SQLite 可留空 DATABASE_URL
# Windows 若 python 命令不可用，用全路径：
# "E:\Env\Python\Python312\python.exe" app.py
python app.py                  # http://localhost:5000/api/health
```

### 前端（Next.js · 端口 3000）
```powershell
cd frontend
Copy-Item .env.local.example .env.local   # NEXT_PUBLIC_API_BASE=http://localhost:5000
npm install    # 首次
npm run dev    # http://localhost:3000
```

> 前后端需**同时运行**。注册/登录后可在浏览器操作记账与提醒。

## 🔑 环境变量
| 变量 | 位置 | 说明 |
|---|---|---|
| DATABASE_URL | backend/.env | 本地留空→SQLite；线上 PostgreSQL |
| AI_PROVIDER | backend/.env | `openai` 或 `anthropic`，默认 openai |
| AI_API_KEY | backend/.env | API Key（也可用旧名 DEEPSEEK_API_KEY） |
| AI_BASE_URL | backend/.env | 接口地址，默认 `https://api.openai.com/v1` |
| AI_MODEL | backend/.env | 模型名，默认 `gpt-4o-mini` |
| NOTIFY_DISPATCH_INTERVAL | backend/.env | 到期提醒后台扫描间隔秒数，默认 60；`0` 关闭 |
| NOTIFY_CRON_SECRET | backend/.env | 可选，外部 cron 调推送接口用 |
| JWT_SECRET | backend/.env | JWT 签名密钥 |
| NEXT_PUBLIC_API_BASE | frontend/.env.local | 后端地址，默认 `http://localhost:5000` |

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
前端 Vercel；后端自建云服务器（Docker Compose：Flask + PostgreSQL + Caddy 自动 HTTPS）。

## 🌐 线上地址
- 前端：_待部署_
- 后端：_待部署_

## 📚 文档
| 文档 | 说明 |
|---|---|
| [docs/需求文档.md](docs/需求文档.md) | 功能需求 FRD v1.1 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计 |
| [docs/API文档.md](docs/API文档.md) | 接口契约 |
| [docs/prompt_log.md](docs/prompt_log.md) | AI Prompt 日志（考核 10%） |
| [docs/研发日志/](docs/研发日志/) | 每日研发总结 |
| [docs/review_checklist.md](docs/review_checklist.md) | 代码审查清单 |

## 🔀 分支说明
- `main`：后端全套（鉴权 / 记账 / 提醒）
- `feat/frontend`：前端开发支线（登录 / 记账页 / 提醒页）
