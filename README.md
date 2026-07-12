# Vita · AI 生活管家

> 一个会「说话」的多用户生活管家。用户注册登录后，选择一个 AI 角色（管家 / 奴才 / 毒舌闺蜜 / 暖心恋人），
> 它用对应语气帮你记账、管日程提醒，并提供情绪价值。

《移动应用项目工程实践》居家实训考核作品。

## ✨ 功能
- 🔐 多用户账号体系（注册/登录，JWT 鉴权，数据按用户隔离）
- 💰 记账理财：记一笔 / 分类 / 收支统计图表
- ⏰ 日程提醒：待办 / 账单 / 到期提醒
- 🤖 AI 管家：角色切换 + 对话 + 每日简报 + 自然语言记账

## 🧱 技术栈
Next.js(App Router+TS+Tailwind) · Flask + SQLAlchemy · PostgreSQL · LangChain + DeepSeek · JWT

## 📁 结构
```
vita/
├── backend/     # Flask + SQLAlchemy + LangChain
├── frontend/    # Next.js
└── docs/        # 需求文档 / 架构 / API / prompt_log / 研发日志 / 审查清单
```

## 🚀 本地运行
```bash
# 后端
cd backend && python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # 填 DATABASE_URL / DEEPSEEK_API_KEY / JWT_SECRET
python app.py               # http://localhost:5000/api/health

# 前端
npx create-next-app@latest frontend --ts --tailwind --app --eslint --src-dir --use-npm
cd frontend && copy .env.local.example .env.local   # NEXT_PUBLIC_API_BASE
npm run dev
```

## 🔑 环境变量
| 变量 | 位置 | 说明 |
|---|---|---|
| DATABASE_URL | backend/.env | 本地 SQLite / 线上 PostgreSQL |
| DEEPSEEK_API_KEY | backend/.env | DeepSeek 密钥 |
| JWT_SECRET | backend/.env | JWT 签名密钥 |
| NEXT_PUBLIC_API_BASE | frontend/.env.local | 后端地址 |

## 📦 部署
前端 Vercel；后端自建云服务器（Docker Compose：Flask + PostgreSQL + Caddy 自动 HTTPS）。

## 🌐 线上地址
- 前端：_待部署_
- 后端：_待部署_

## 📚 文档
需求 [docs/需求文档.md](docs/需求文档.md) · 架构 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · API [docs/API文档.md](docs/API文档.md)
