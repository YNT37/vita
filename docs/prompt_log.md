# Prompt 日志（考核 10%）

> 规则：**每条 Prompt 必须附 AI 原始输出**（截图或代码块），并标注**对应功能/文件**。边做边记。

## 模板
```
### #序号 · YYYY-MM-DD · 工具/模型：Cursor(Claude Sonnet) 等
- 对应功能/文件：<例如 backend/blueprints/finance.py>
- Prompt：
  > （输入的完整提示词）
- AI 原始输出：
  > （AI 返回原文 / 代码块 / 截图路径）
- 采纳情况：全部采纳 / 部分修改（说明）
```

---

### #1 · 2026-07-12 · 规划
- 对应功能/文件：整体架构、需求、任务规划
- Prompt：
  > （粘贴你的规划 prompt）
- AI 原始输出：
  > （见 docs/需求文档.md、docs/ARCHITECTURE.md）
- 采纳情况：采纳。

---

### #2 · 2026-07-12 · Cursor(Claude) · 后端骨架
- 对应功能/文件：`backend/config.py`、`extensions.py`、`models.py`、`errors.py`、`app.py`、`requirements.txt`、`.env.example`
- Prompt：
  > 按 docs/ARCHITECTURE.md 的目录结构、docs/API文档.md 的契约，创建 Day1 后端骨架：config/extensions/models/errors/app + requirements + .env.example；本地先用 SQLite，统一错误体 {"error":{"code","message","field?"}}，GET /api/health 返回 {"status":"ok"}。
- AI 原始输出：
  > 生成上述 8 个文件：create_app 工厂初始化 db/jwt/cors 并注册蓝图与错误处理；六张表 users/categories/transactions/reminders/chat_messages/settings（密码 werkzeug 哈希）；ApiError 统一异常 + 400/404/405/500 兜底 + JWT 未授权/过期/无效统一 401。（原始输出见本次 Cursor 对话截图）
- 采纳情况：全部采纳。

### #3 · 2026-07-12 · Cursor(Claude) · 注册/登录/鉴权
- 对应功能/文件：`backend/blueprints/auth.py`
- Prompt：
  > 实现账号与鉴权蓝图：POST /api/auth/register（用户名唯一→重复409、密码<6→400）、POST /api/auth/login（校验后签发 JWT、错误→401）、GET /api/me（需 JWT）。
- AI 原始输出：
  > auth_bp + me_bp；werkzeug.security 哈希；create_access_token(identity=str(user.id))；所有异常走 ApiError，输出格式与业务错误一致。（原始输出见本次 Cursor 对话截图）
- 采纳情况：全部采纳。

### #4 · 2026-07-12 · Cursor(Claude) · 记账接口与统计
- 对应功能/文件：`backend/blueprints/finance.py`
- Prompt：
  > 实现记账蓝图：POST/GET/DELETE /api/transactions + GET /api/stats/summary，全部按 user_id 隔离；校验 type∈{income,expense}、amount 为数字且 0<amount≤1亿、date 为 YYYY-MM-DD，非法→400；越权/不存在→404。
- AI 原始输出：
  > finance_bp；Decimal 校验金额（含 NaN、上限）；按月左闭右开区间聚合 income/expense/byCategory/byDay；删除仅限本人、否则 404。（原始输出见本次 Cursor 对话截图）
- 采纳情况：全部采纳。

### #5 · 2026-07-12 · Cursor(Claude) · 提醒（日程）接口
- 对应功能/文件：`backend/blueprints/reminders.py`、`backend/app.py`（注册蓝图）
- Prompt：
  > 实现提醒蓝图 reminders_bp（需 JWT、按 user_id 隔离）：GET /api/reminders（按 due_at 升序）、POST /api/reminders {title,due_at,type(bill/life/anniversary),note}（title 空/超长→400、due_at 非法→400、type 非法→400）、PATCH /api/reminders/<id>（切换 done，可选改 title/due_at/type/note）、DELETE /api/reminders/<id>（越权/不存在→404）。并在 app.py 注册该蓝图。
- AI 原始输出：
  > reminders_bp；due_at 兼容多种 ISO 格式解析；四个接口全部按 user_id 过滤；PATCH 支持 done 切换与字段编辑；越权/不存在统一 404；已在 create_app 注册。（原始输出见本次 Cursor 对话截图）
- 采纳情况：全部采纳。

### #6 · 2026-07-12 · Cursor(Claude) · 前端 API 客户端与登录/注册
- 对应功能/文件：`frontend/src/lib/api.ts`、`lib/auth.tsx`、`app/login/page.tsx`、`app/register/page.tsx`、`app/layout.tsx`、`app/page.tsx`、`.env.local(.example)`
- Prompt：
  > 在 Next.js(App Router + TS + Tailwind v4) 前端实现：lib/api.ts（读 NEXT_PUBLIC_API_BASE，fetch 封装，自动带 Bearer，统一解析 {error:{code,message,field}}）；lib/auth.tsx（AuthProvider + useAuth，token 存 localStorage，挂载时用 /api/me 恢复登录态）；/login、/register 页面（表单校验、错误提示、成功跳仪表盘）；layout 挂 AuthProvider；首页做登录守卫（未登录跳 /login）。
- AI 原始输出：
  > 生成上述文件：ApiError 类透传后端错误码与 field；注册后自动登录；首页展示用户名 + 退出登录 + 功能入口卡片；未登录自动跳 /login。（原始输出见本次 Cursor 对话截图）
- 采纳情况：全部采纳。
