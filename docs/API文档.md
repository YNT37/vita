# Vita API 文档（契约）

- Base URL：`{NEXT_PUBLIC_API_BASE}`，本地默认 `http://localhost:5000`，前缀 `/api`
- 返回 JSON；错误统一 `{"error":{"code","message","field?"}}`
- 除 `auth/*` 和 `health` 外，均需请求头 `Authorization: Bearer <token>`，并按当前用户隔离数据
- 日期 `YYYY-MM-DD`

## 一、鉴权 Auth

### `POST /api/auth/register`
```json
{ "username":"alex", "password":"secret123" }
// 201 → { "id":1, "username":"alex" }
```
用户名唯一（重复→409）；密码 ≥6 位（否则→400）。

### `POST /api/auth/login`
```json
{ "username":"alex", "password":"secret123" }
// 200 → { "token":"<jwt>", "user":{ "id":1,"username":"alex" } }
```
密码错误→401。

### `GET /api/me`
需 JWT。`200 → { "id":1, "username":"alex" }`；无/失效 token→401。

## 二、记账 Transactions（需 JWT）

- `GET /api/transactions?month=YYYY-MM` → 列表（仅本人）
- `POST /api/transactions` `{type(income/expense),amount>0,category,note,date}` → 201
- `DELETE /api/transactions/<id>` → `{"ok":true}`；不存在/越权→404
- `GET /api/stats/summary?month=` → `{income,expense,byCategory[],byDay[]}`

校验：type 合法、amount 数字且>0、date 合法，非法→400。

## 三、提醒 Reminders（需 JWT）

- `GET /api/reminders` → 列表（仅本人）
- `POST /api/reminders` `{title,due_at,type(bill/life/anniversary),note}` → 201（title 空/日期非法→400）
- `PATCH /api/reminders/<id>` `{done:true}` → 200
- `DELETE /api/reminders/<id>` → `{"ok":true}`；不存在/越权→404

## 四、AI 管家（需 JWT）

- `GET /api/persona` → `{current,options:["butler","servant","sassy","lover"]}`
- `POST /api/persona` `{persona}` → `{current}`（未知角色→400）
- `GET /api/settings` → `{persona,persona_options,ai_provider,ai_provider_options,ai_configured,ai_api_key_set,ai_api_key_hint,ai_base_url,ai_model,...}`
- `POST /api/settings` `{persona?,ai_provider?,ai_api_key?,ai_base_url?,ai_model?}` → 同上（传空字符串可清除用户侧配置）
- `ai_provider`：`openai`（需 Key+Base URL+Model）或 `anthropic`（需 Key+Model，Base URL 可选）
- `POST /api/ai/chat` `{message}` → `{reply}`（空→400）
- `POST /api/ai/brief` → `{text}`（聚合当日数据，角色语气播报）
- `POST /api/ai/parse` `{text}` → `{intent:"transaction|reminder|unknown", data:{...}}`

健壮性：AI 空输入/超时/Key 失效/非法返回 → 降级文案，绝不 500。

## 五、健康检查
`GET /api/health` → `{"status":"ok"}`（无需 JWT）。
