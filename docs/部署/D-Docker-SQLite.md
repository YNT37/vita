# 方式 D · Docker Compose（SQLite + Caddy）

同机容器跑前端 + 后端，Caddy 在 **80** 端口同域反代。返回 [部署索引](./README.md)。

**前置**：Docker + Compose 插件；安全组放行 **80**。

相关：[环境变量](./环境变量说明.md) · [常见问题](./常见问题.md)  
编排文件：仓库根目录 `docker-compose.yml`、`deploy/Caddyfile`

---

## 步骤

### 1. 克隆

```bash
git clone https://github.com/YNT37/vita.git
cd vita
```

### 2. `backend/.env`

```bash
cp backend/.env.example backend/.env
vim backend/.env
```

```env
SECRET_KEY=随机串
JWT_SECRET=另一随机串
# DATABASE_URL 可不管：compose 会注入容器内 SQLite 卷路径
# 可选 AI_API_KEY 等
CORS_ORIGINS=*
```

无需 `deploy/.env`（此方式不用 venv 脚本）。

### 3. 构建并启动

```bash
docker compose up -d --build
curl -s http://127.0.0.1/api/health
# 浏览器：http://公网IP/
```

Caddy：`/` → 前端，`/api` → 后端。

### 4. 更新

```bash
git pull origin main
docker compose up -d --build
```

### 5. 日志与停止

```bash
docker compose logs -f backend
docker compose down
```

数据在 Docker 卷 `vita_data`：`docker volume ls`。

---

## 检查清单

- [ ] 密钥已改
- [ ] 安全组放行 80
- [ ] `/api/health` 与浏览器注册登录正常

需要 Postgres → [方式 E](./E-Docker-PostgreSQL.md)。
