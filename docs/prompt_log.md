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

---

### #9 · 2026-07-13 · Cursor(Claude) · AI 服务层（角色 prompt + LangChain + 降级）
- 对应功能/文件：`backend/services/prompts.py`、`backend/services/ai_service.py`、`backend/requirements.txt`
- Prompt：
  > 按 docs/ARCHITECTURE.md 第 5 节创建 AI 服务层：prompts.py 含 4 角色 system prompt 与 chat/brief 静态兜底文案；ai_service.py 实现 generate_chat_reply、generate_brief、parse_input，LangChain ChatOpenAI 接 DeepSeek（惰性初始化、timeout 25s）；无 Key/超时/异常/非法 JSON 一律降级；history 最近 6 轮、单条截断 500 字；parse 先 LLM JSON 再正则兜底（「午饭30」→transaction、「提醒我…」→reminder）。requirements 补 langchain/langchain-openai/pydantic。
- AI 原始输出：

```python
# services/prompts.py（摘录）
PERSONA_OPTIONS = ("butler", "servant", "sassy", "lover")
SYSTEM_PROMPTS = {"butler": "你是 Vita 生活管家...", ...}
FALLBACK_CHAT = {"butler": "您说得是。我这边暂时无法连接 AI 服务...", ...}

# services/ai_service.py（摘录）
def _get_llm():
    if not api_key: return None
    _LLM = ChatOpenAI(base_url="https://api.deepseek.com", model="deepseek-chat", timeout=25)

def generate_chat_reply(persona, message, history):
    reply = _invoke_llm(SYSTEM_PROMPTS[persona], user_prompt)
    return reply or FALLBACK_CHAT[persona]

def parse_input(text):
    result = _llm_parse(text)
    if result and result["intent"] != "unknown": return result
- 采纳情况：全部采纳。

---

### #10 · 2026-07-13 · Cursor(Claude) · AI 管家 HTTP 接口
- 对应功能/文件：`backend/blueprints/ai.py`、`backend/app.py`
- Prompt：
  > 实现 ai 蓝图并注册：GET/POST /api/persona（settings 表存当前角色，未知→400）；POST /api/ai/chat（空 message→400，读 chat_messages 历史调 generate_chat_reply，存 user/assistant 消息）；POST /api/ai/brief（聚合当日交易与未完成提醒调 generate_brief）；POST /api/ai/parse（空 text→400，调 parse_input）。均需 JWT。
- AI 原始输出：

```python
@ai_bp.post("/ai/chat")
@jwt_required()
def ai_chat():
    message = (data.get("message") or "").strip()
    if not message: raise ApiError("invalid_message", "消息不能为空", 400, "message")
    persona = _get_persona(_uid())
    reply = generate_chat_reply(persona, message, _load_history(uid, persona))
    db.session.add(ChatMessage(..., role="user", ...))
    db.session.add(ChatMessage(..., role="assistant", content=reply, ...))
    return jsonify({"reply": reply}), 200

@ai_bp.post("/ai/brief")
def ai_brief():
    context = _today_brief_context(uid)  # 当日交易 + 未完成提醒
    return jsonify({"text": generate_brief(persona, context)}), 200
```

- 采纳情况：全部采纳。

---

### #11 · 2026-07-13 · Cursor(Claude) · 前端 AI 管家页
- 对应功能/文件：`frontend/src/app/persona/page.tsx`、`frontend/src/app/page.tsx`
- Prompt：
  > 实现 /persona 页面（需登录守卫）：GET/POST /api/persona 角色切换；POST /api/ai/brief 今日播报区；POST /api/ai/chat 对话气泡 UI；POST /api/ai/parse 自然语言解析预览，确认后写入 /api/transactions 或 /api/reminders；loading/error 三态；样式对齐现有页面。仪表盘去掉「将陆续上线」文案。
- AI 原始输出：

```tsx
// persona/page.tsx（摘录）
async function switchPersona(id) {
  await apiFetch("/api/persona", { method: "POST", body: { persona: id } });
  setMessages([]);
  await loadBrief();
}

// 对话
const res = await apiFetch("/api/ai/chat", { method: "POST", body: { message: text } });
setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);

// 解析 + 确认写入
const parsed = await apiFetch("/api/ai/parse", { method: "POST", body: { text } });
if (parsed.intent === "transaction") await apiFetch("/api/transactions", { method: "POST", body: parsed.data });
```

- 采纳情况：全部采纳。

---

### #12 · 2026-07-13 · Cursor(Claude) · 前端布局重构（管家主页 + 设置页）
- 对应功能/文件：`frontend/src/app/page.tsx`、`settings/page.tsx`、`components/AppShell.tsx`；`backend/blueprints/settings.py`、`services/user_settings.py`
- Prompt：
  > 重构布局：/ 为 AI 管家主页；/settings 放性格与 API Key；底部导航；/persona 重定向。后端 GET/POST /api/settings，用户 Key 存库并优先用于 AI 调用。
- AI 原始输出：

```tsx
// AppShell 底部导航：管家 / 记账 / 提醒 / 设置
// settings 页：性格四选一 + DeepSeek API Key 密码框 + 保存
```

```python
@settings_bp.post("/settings")
def update_settings():
    set_persona(uid, persona)
    set_user_api_key(uid, deepseek_api_key)  # 空字符串清除
```

- 采纳情况：全部采纳。

---

### #13 · 2026-07-13 · Cursor(Claude) · AI 接口改为 OpenAI 通用格式
- 对应功能/文件：`backend/config.py`、`services/ai_service.py`、`services/user_settings.py`、`blueprints/settings.py`、`blueprints/ai.py`；`frontend/src/app/settings/page.tsx`；`backend/.env.example`；`docs/API文档.md`
- Prompt：
  > 先不急着上传，api 接口不一定用 deepseek，可以用 openai 通用接口
- AI 原始输出：

```python
# config.py
AI_API_KEY = os.getenv("AI_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

def resolve_ai_config(user_id):
    return {"api_key": ..., "base_url": ..., "model": ..., "configured": bool(...)}

def _get_llm(api_key, base_url, model):
    llm = ChatOpenAI(base_url=resolved_base, api_key=resolved_key, model=resolved_model, timeout=25)
```

```tsx
// settings 页：API Key + Base URL + Model 三字段
<input value={baseUrl} placeholder="https://api.openai.com/v1" />
<input value={model} placeholder="gpt-4o-mini / deepseek-chat" />
```

- 采纳情况：全部采纳。DeepSeek 仍可作为兼容端点，通过 Base URL + Model 配置即可。

---

### #14 · 2026-07-13 · Cursor(Claude) · 新增 Anthropic 接口
- 对应功能/文件：`backend/config.py`、`services/ai_service.py`、`services/user_settings.py`、`blueprints/settings.py`；`frontend/src/app/settings/page.tsx`；`backend/requirements.txt`、`backend/.env.example`；`docs/API文档.md`、`README.md`
- Prompt：
  > 再添加一个 Anthropic 接口吧
- AI 原始输出：

```python
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai | anthropic

def _get_llm(provider, api_key, base_url, model):
    if provider == "anthropic":
        llm = ChatAnthropic(model=resolved_model, api_key=resolved_key, base_url=resolved_base or None)
    else:
        llm = ChatOpenAI(base_url=resolved_base, api_key=resolved_key, model=resolved_model)
```

```tsx
// settings 页：接口类型二选一
<button onClick={() => switchProvider("openai")}>OpenAI 兼容</button>
<button onClick={() => switchProvider("anthropic")}>Anthropic</button>
```

- 采纳情况：全部采纳。Anthropic 仅需 Key + Model；Base URL 留空走官方端点，代理时可填。

---

### #15 · 2026-07-13 · Cursor(Claude) · 统计中心与分类/资产管理
- 对应功能/文件：`frontend/src/app/stats/page.tsx`、`backend/blueprints/overview.py`、`categories.py`、`services/category_service.py`、`services/user_context.py`；`models.py`（UserCategory）；`AppShell.tsx`、`records/page.tsx`；`docs/API文档.md`
- Prompt：
  > 还需要建立一个统计页面，可以设置分类、账户信息等，可以查看资产视图、待办事件等，也方便ai记入数据、调用数据，或理解意图
- AI 原始输出：

```python
@overview_bp.get("/overview")
def get_overview():
    return jsonify({month, stats, assets, assets_total, reminders_pending, categories})

class UserCategory(db.Model):
    user_id, name, kind  # expense/income
```

```tsx
// /stats 四 Tab：概览 / 资产 / 待办 / 分类
```

- 采纳情况：全部采纳。AI 上下文通过 `build_user_context()` 注入分类、资产、月度统计与待办。

---

### #16 · 2026-07-13 · Cursor(Claude) · 跨页面数据同步
- 对应功能/文件：`frontend/src/lib/data-refresh.tsx`、`layout.tsx`；`page.tsx`、`records/page.tsx`、`stats/page.tsx`、`reminders/page.tsx`
- Prompt：
  > 让ai记账无法同步到其他页面
- AI 原始输出：

```tsx
// DataRefreshProvider + bump() 全局刷新信号
// AI chat 返回 action 时 bump()；各页 useAutoReload(load) 监听 version 与路由切换
```

- 采纳情况：全部采纳。

---

### #17 · 2026-07-13 · Cursor(Claude) · 聊天记录持久化加载
- 对应功能/文件：`backend/blueprints/ai.py`（GET /api/ai/chat/history）；`frontend/src/app/page.tsx`
- Prompt：
  > 每次切换页面ai聊天记录就没了
- AI 原始输出：

```python
@ai_bp.get("/ai/chat/history")
def ai_chat_history():
    return jsonify({"persona": persona, "messages": [...]})
```

```tsx
await apiFetch("/api/ai/chat/history");
setMessages(res.messages);
```

- 采纳情况：全部采纳。对话按角色分库存储，切页回来自动加载。

---

### #18 · 2026-07-13 · Cursor(Claude) · 批量财务写入防编造
- 对应功能/文件：`backend/services/ai_service.py`、`prompts.py`、`blueprints/ai.py`；`frontend/src/app/page.tsx`、`lib/persona.ts`
- Prompt：
  > AI 有记录数据但是统计、记账、提醒都没数据（基金/微信/建行/工行 + 花呗/白条）
- AI 原始输出：

```python
# intent=batch + actions[] 一次写入多账户余额与还款提醒
# 多账户汇报优先规则提取，禁止仅凭聊天记录复述未入库数字
actions = _regex_extract_batch(text)  # 基金/微信/... + 花呗还款提醒
```

- 采纳情况：全部采纳。根因是 AI 闲聊复述未落库；现支持批量写入并强制以系统数据为准。

---

### #19 · 2026-07-13 · Cursor(Claude) · 修复口语账户名与同步指令落库
- 对应功能/文件：`backend/services/ai_service.py`、`blueprints/ai.py`；`frontend/src/app/page.tsx`、`records/page.tsx`
- Prompt：
  > 还是不行啊？（用户原话：建设银行卡/工商银行卡、花呗欠款、还款日期7.25、帮我同步）
- AI 原始输出：

```python
# 建设银行→建行，欠款→欠，7.25→日期；「同步/需要」从历史用户消息找回明细再 batch 写入
understanding = understand_message(message, context, ai_cfg, history_text=...)
```

- 采纳情况：全部采纳。并说明「记账页」只显示流水，资产在「统计→资产」。

---

### #20 · 2026-07-13 · Cursor(Claude) · 统计中心可自由编辑维护
- 对应功能/文件：`frontend/src/app/stats/page.tsx`；`backend` assets PATCH、categories PATCH、Asset.kind；`overview` 净资产拆分
- Prompt：
  > 统计列表需要强自定义性，可以自由修改各种数据，方便用户维护信息
- AI 原始输出：

```tsx
// 账户/待办/分类均支持新增、行内编辑、删除；账户可标资产/负债
await apiFetch(`/api/assets/${id}`, { method: "PATCH", body: { name, balance, kind, note } });
```

- 采纳情况：全部采纳。
