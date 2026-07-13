# 方式 C · 云服务器（venv + PostgreSQL）

在 [方式 B](./B-云服务器-venv-SQLite.md) 基础上把数据库换成 PostgreSQL。返回 [部署索引](./README.md)。

**前置**：同方式 B，外加已按 [数据库说明](./数据库-SQLite与PostgreSQL.md) 装好 Postgres（系统包或 Docker 单容器）。

相关：[环境变量](./环境变量说明.md) · [常见问题](./常见问题.md)

---

## 步骤

### 1. 准备 PostgreSQL

二选一：

- 系统安装：见 [数据库说明 §2](./数据库-SQLite与PostgreSQL.md)
- Docker 只跑库：见 [数据库说明 §3](./数据库-SQLite与PostgreSQL.md)

确认本机可连：

```bash
psql "postgresql://vita:你的强密码@127.0.0.1:5432/vita" -c 'SELECT 1;'
```

### 2. 克隆与 `deploy/.env`（同方式 B）

```bash
git clone https://github.com/YNT37/vita.git
cd vita
cp deploy/.env.example deploy/.env
vim deploy/.env
# PUBLIC_HOST=公网IP
```

### 3. `backend/.env`（关键：填 DATABASE_URL）

```bash
cp backend/.env.example backend/.env
vim backend/.env
```

```env
SECRET_KEY=随机串
JWT_SECRET=另一随机串
DATABASE_URL=postgresql://vita:你的强密码@127.0.0.1:5432/vita
CORS_ORIGINS=*
# 可选 AI_*
```

### 4. 启动

```bash
chmod +x deploy/*.sh
./deploy/venv-setup.sh
./deploy/venv-start.sh
curl -s http://127.0.0.1:5000/api/health
# 浏览器 http://公网IP:3000 — 重新注册（空库）
```

### 5. 更新 / 停止

```bash
./deploy/pull-and-up.sh
./deploy/venv-stop.sh
```

---

## 从 SQLite 换过来

没有自动迁移。考核演示建议直接空库重来。备份 Postgres 用 `pg_dump`（见数据库说明）。

---

## 检查清单

- [ ] `psql` 能连上
- [ ] `DATABASE_URL` 密码正确
- [ ] 5432 **未**对公网开放
- [ ] 前端能注册登录
