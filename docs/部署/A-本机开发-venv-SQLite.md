# 方式 A · 本机开发（venv + SQLite）

适合日常写代码。返回 [部署索引](./README.md)。

**前置**：Python 3.10+、Node 18+。

相关：[环境变量](./环境变量说明.md) · [数据库](./数据库-SQLite与PostgreSQL.md) · [常见问题](./常见问题.md)

---

## 步骤

### 1. 后端

```bash
cd backend
python3 -m venv .venv          # Windows: python -m venv .venv
source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
vim .env
# DATABASE_URL 留空即可
# 按需填 AI_API_KEY
python app.py
# 健康检查：http://127.0.0.1:5000/api/health
```

### 2. 前端（另开终端）

```bash
cd frontend
echo 'NEXT_PUBLIC_API_BASE=http://localhost:5000' > .env.local
npm install
npm run dev
# http://localhost:3000
```

前后端需同时运行。

---

## 本机改用 PostgreSQL（可选）

1. 按 [数据库说明](./数据库-SQLite与PostgreSQL.md) §2 或 §3 建库。  
2. `backend/.env` 填写 `DATABASE_URL=postgresql://...`。  
3. 重启 `python app.py`，重新注册账号。

---

## 检查清单

- [ ] `/api/health` 返回 `{"status":"ok"}`
- [ ] 浏览器能注册、登录、记一笔
