# 方式 B · 云服务器（venv + SQLite）

适合考核快速演示。返回 [部署索引](./README.md)。

**前置**：公网 IP；已装 `git`、`python3`、`python3-venv`、Node.js 18+ / npm；安全组放行 **3000、5000**。

相关：[环境变量](./环境变量说明.md) · [数据库·SQLite](./数据库-SQLite与PostgreSQL.md) · [常见问题](./常见问题.md)

---

## 步骤

### 1. 克隆

```bash
git clone https://github.com/YNT37/vita.git
cd vita
```

### 2. 部署配置 `deploy/.env`

```bash
cp deploy/.env.example deploy/.env
vim deploy/.env
```

至少设置：

```env
PUBLIC_HOST=你的公网IP
BACKEND_PORT=5000
FRONTEND_PORT=3000
# 已有 venv 可填：VENV_DIR=/path/to/.venv
```

### 3. 后端配置 `backend/.env`

```bash
cp backend/.env.example backend/.env
vim backend/.env
```

```env
SECRET_KEY=用 openssl rand -hex 32 生成
JWT_SECRET=再生成一串，不要相同
DATABASE_URL=
# 留空 = SQLite → backend/vita.db
# 可选 AI_API_KEY / AI_BASE_URL / AI_MODEL
CORS_ORIGINS=*
```

### 4. 安装依赖并启动

```bash
chmod +x deploy/*.sh
./deploy/venv-setup.sh
./deploy/venv-start.sh
```

### 5. 验证

```bash
curl -s http://127.0.0.1:5000/api/health
# 浏览器：http://公网IP:3000
```

---

## 日常运维

```bash
# 更新代码并重启
cd ~/vita
./deploy/pull-and-up.sh

# 停止
./deploy/venv-stop.sh

# 日志
tail -f deploy/run/backend.log
tail -f deploy/run/frontend.log
```

SQLite 备份：复制 `backend/vita.db`。

---

## 检查清单

- [ ] `SECRET_KEY` / `JWT_SECRET` 已改
- [ ] `PUBLIC_HOST` 正确，改后重新执行过 `venv-start.sh`
- [ ] 安全组放行 3000 / 5000
- [ ] 能注册登录、记一笔

需要更稳的库 → [方式 C](./C-云服务器-venv-PostgreSQL.md)。
