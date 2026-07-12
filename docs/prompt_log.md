# Prompt 日志（考核 10%）

> 规则：每条 Prompt 附 AI 返回的**原始输出**（代码块摘录），并标注对应功能/文件，便于与代码对照审查。

## 模板
```
### #序号 · YYYY-MM-DD · 工具/模型：Cursor(Claude)
- 对应功能/文件：<文件路径>
- Prompt：（完整提示词）
- AI 原始输出：（代码块 / 原文摘录）
- 采纳情况：全部采纳 / 部分修改
```

---

### #1 · 2026-07-12 · Cursor(Claude) · 项目规划
- 对应功能/文件：`docs/需求文档.md`、`docs/ARCHITECTURE.md`、`docs/API文档.md`、`README.md`
- Prompt：
  > 项目是「Vita · AI 生活管家」居家实训考核作品。技术栈：Next.js + Flask + PostgreSQL + LangChain/DeepSeek + JWT 多用户鉴权。请输出完整功能需求文档（含多用户、记账、提醒、AI 角色、验收标准）、架构设计（含 mermaid 图、目录结构、AI 服务设计、自建部署方案）、API 契约文档、README 运行指南。
- AI 原始输出：
  > 生成 FRD v1.1：6 个前端路由、JWT 横切鉴权、4 个 AI 角色、自然语言录入、降级兜底要求；架构文档含前后端分离 mermaid、blueprints/services 目录、六张数据表、Docker+Caddy 部署图；API 文档列出 auth/transactions/reminders/ai 全部端点与错误格式 `{"error":{"code","message","field?"}}`。
- 采纳情况：全部采纳。

---

### #2 · 2026-07-12 · Cursor(Claude) · 后端骨架
- 对应功能/文件：`backend/config.py`、`extensions.py`、`models.py`、`errors.py`、`app.py`、`requirements.txt`、`.env.example`
- Prompt：
  > 按 docs/ARCHITECTURE.md 的目录结构、docs/API文档.md 的契约，创建 Day1 后端骨架：config/extensions/models/errors/app + requirements + .env.example；本地先用 SQLite，统一错误体 {"error":{"code","message","field?"}}，GET /api/health 返回 {"status":"ok"}。
- AI 原始输出：

```python
# backend/app.py（摘录）
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    register_error_handlers(app)
    register_jwt_error_handlers(jwt)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()
    return app
```

```python
# backend/errors.py（摘录）
class ApiError(Exception):
    def __init__(self, code, message, status=400, field=None):
        self.code, self.message, self.status, self.field = code, message, status, field
    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message}}
        if self.field: body["error"]["field"] = self.field
        return jsonify(body), self.status
```

- 采纳情况：全部采纳。

---

### #3 · 2026-07-12 · Cursor(Claude) · 注册/登录/鉴权
- 对应功能/文件：`backend/blueprints/auth.py`
- Prompt：
  > 实现账号与鉴权蓝图：POST /api/auth/register（用户名唯一→重复409、密码<6→400）、POST /api/auth/login（校验后签发 JWT、错误→401）、GET /api/me（需 JWT）。
- AI 原始输出：

```python
@auth_bp.post("/register")
def register():
    username, password = _get_credentials()
    if not username or len(username) > 64:
        raise ApiError("invalid_username", "用户名不能为空且不超过64位", 400, "username")
    if len(password) < 6 or len(password) > 128:
        raise ApiError("invalid_password", "密码长度需为 6-128 位", 400, "password")
    if User.query.filter_by(username=username).first():
        raise ApiError("username_taken", "用户名已存在", 409, "username")
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@auth_bp.post("/login")
def login():
    ...
    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200
```

- 采纳情况：全部采纳。

---

### #4 · 2026-07-12 · Cursor(Claude) · 记账接口与统计
- 对应功能/文件：`backend/blueprints/finance.py`
- Prompt：
  > 实现记账蓝图：POST/GET/DELETE /api/transactions + GET /api/stats/summary，全部按 user_id 隔离；校验 type∈{income,expense}、amount 为数字且 0<amount≤1亿、date 为 YYYY-MM-DD，非法→400；越权/不存在→404。
- AI 原始输出：

```python
@finance_bp.post("/transactions")
@jwt_required()
def create_transaction():
    ...
    amount = Decimal(str(data.get("amount")))
    if not amount.is_finite() or amount <= 0 or amount > Decimal("100000000"):
        raise ApiError("invalid_amount", "金额需大于 0 且不超过 1 亿", 400, "amount")
    txn = Transaction(user_id=_uid(), type=t_type, amount=amount, ...)
    db.session.add(txn)
    db.session.commit()
    return jsonify(txn.to_dict()), 201

@finance_bp.get("/stats/summary")
@jwt_required()
def stats_summary():
    ...
    return jsonify({
        "income": float(income), "expense": float(expense),
        "byCategory": [...], "byDay": [...]
    }), 200
```

- 采纳情况：全部采纳。

---

### #5 · 2026-07-12 · Cursor(Claude) · 提醒（日程）接口
- 对应功能/文件：`backend/blueprints/reminders.py`、`backend/app.py`
- Prompt：
  > 实现提醒蓝图 reminders_bp（需 JWT、按 user_id 隔离）：GET /api/reminders（按 due_at 升序）、POST /api/reminders {title,due_at,type(bill/life/anniversary),note}、PATCH /api/reminders/<id>（切换 done）、DELETE /api/reminders/<id>（越权/不存在→404）。并在 app.py 注册该蓝图。
- AI 原始输出：

```python
@reminders_bp.post("/reminders")
@jwt_required()
def create_reminder():
    title = _validate_title(data.get("title"))
    due_at = _parse_due(data.get("due_at"))
    r_type = _validate_type(data.get("type") or "life")
    reminder = Reminder(user_id=_uid(), title=title, due_at=due_at, type=r_type, ...)
    db.session.add(reminder)
    db.session.commit()
    return jsonify(reminder.to_dict()), 201

@reminders_bp.patch("/reminders/<int:reminder_id>")
@jwt_required()
def update_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=_uid()).first()
    if not reminder: raise ApiError("not_found", "提醒不存在", 404)
    if "done" in data: reminder.done = bool(data["done"])
    ...
```

- 采纳情况：全部采纳。

---

### #6 · 2026-07-12 · Cursor(Claude) · 前端 API 客户端与登录/注册
- 对应功能/文件：`frontend/src/lib/api.ts`、`lib/auth.tsx`、`app/login/page.tsx`、`app/register/page.tsx`、`app/layout.tsx`、`app/page.tsx`
- Prompt：
  > 在 Next.js(App Router + TS + Tailwind v4) 前端实现：lib/api.ts（读 NEXT_PUBLIC_API_BASE，fetch 封装，自动带 Bearer，统一解析 {error:{code,message,field}}）；lib/auth.tsx（AuthProvider + useAuth，token 存 localStorage）；/login、/register 页面；layout 挂 AuthProvider；首页做登录守卫。
- AI 原始输出：

```typescript
// frontend/src/lib/api.ts（摘录）
export async function apiFetch<T>(path: string, { method = "GET", body, auth = true } = {}) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    const err = (await res.json())?.error;
    throw new ApiError(res.status, err?.code ?? "error", err?.message ?? "请求失败", err?.field);
  }
  return res.json() as T;
}
```

```typescript
// frontend/src/lib/auth.tsx（摘录）
const login = useCallback(async (username, password) => {
  const res = await apiFetch<{ token: string; user: User }>("/api/auth/login",
    { method: "POST", body: { username, password }, auth: false });
  setToken(res.token);
  setUser(res.user);
}, []);
```

- 采纳情况：全部采纳。

---

### #7 · 2026-07-12 · Cursor(Claude) · 前端提醒页
- 对应功能/文件：`frontend/src/app/reminders/page.tsx`
- Prompt：
  > 实现 /reminders 提醒页（需登录守卫）：GET /api/reminders 列表；新增表单调 POST；勾选切换 done 调 PATCH；删除调 DELETE；loading/error/empty 三态；3 天内到期高亮。
- AI 原始输出：

```tsx
// frontend/src/app/reminders/page.tsx（摘录）
const load = useCallback(async () => {
  const list = await apiFetch<Reminder[]>("/api/reminders");
  setItems(list);
}, []);

async function toggleDone(item: Reminder) {
  const updated = await apiFetch<Reminder>(`/api/reminders/${item.id}`, {
    method: "PATCH", body: { done: !item.done },
  });
  setItems((prev) => prev.map((r) => (r.id === item.id ? updated : r)));
}

// 临期高亮
const soon = !item.done && isDueSoon(item.due_at);
```

- 采纳情况：全部采纳。

---

### #8 · 2026-07-12 · Cursor(Claude) · 前端记账页
- 对应功能/文件：`frontend/src/app/records/page.tsx`
- Prompt：
  > 实现 /records 记账页（需登录守卫）：月份选择器；GET /api/stats/summary 展示收入/支出/结余；记一笔表单调 POST /api/transactions；列表 + DELETE；loading/error/empty 三态。
- AI 原始输出：

```tsx
// frontend/src/app/records/page.tsx（摘录）
const [list, summary] = await Promise.all([
  apiFetch<Transaction[]>(`/api/transactions?month=${month}`),
  apiFetch<StatsSummary>(`/api/stats/summary?month=${month}`),
]);

async function onCreate(e: React.FormEvent) {
  await apiFetch<Transaction>("/api/transactions", {
    method: "POST",
    body: { type, amount: num, category: category.trim(), note, date },
  });
  await load();  // 刷新列表与统计
}

// 统计卡片
<StatCard label="本月收入" value={formatMoney(stats.income)} color="text-green-600" />
<StatCard label="本月支出" value={formatMoney(stats.expense)} color="text-red-500" />
<StatCard label="结余" value={formatMoney(balance)} />
```

- 采纳情况：全部采纳。
