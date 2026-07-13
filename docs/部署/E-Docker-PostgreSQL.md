# 方式 E · Docker Compose + PostgreSQL

全容器：Postgres + Flask + Next + Caddy（**:80**）。返回 [部署索引](./README.md)。

**前置**：Docker + Compose；安全组放行 **80**。

相关：[环境变量](./环境变量说明.md) · [常见问题](./常见问题.md)  
编排文件：`docker-compose.postgres.yml`、`deploy/postgres.env.example`、`deploy/Caddyfile`

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
SECRET_KEY=请改成随机串
JWT_SECRET=请改成另一随机串
DATABASE_URL=postgresql://vita:请改密码@db:5432/vita
CORS_ORIGINS=*
# 可选 AI_*
```

注意：主机名必须是 **`db`**（compose 服务名），不是 `127.0.0.1`。

### 3. 数据库密码 `deploy/postgres.env`

```bash
cp deploy/postgres.env.example deploy/postgres.env
vim deploy/postgres.env
```

```env
POSTGRES_USER=vita
POSTGRES_PASSWORD=请改密码
POSTGRES_DB=vita
```

**`POSTGRES_PASSWORD` 必须与 `DATABASE_URL` 里密码一致。**

### 4. 启动

```bash
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env up -d --build
curl -s http://127.0.0.1/api/health
# 浏览器：http://公网IP/
```

### 5. 更新

```bash
git pull origin main
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env up -d --build
```

### 6. 日志 / 停止

```bash
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env logs -f
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env down
# 加 -v 会删掉数据库卷，慎用
```

---

## 检查清单

- [ ] 两处密码一致
- [ ] `DATABASE_URL` 使用主机名 `db`
- [ ] 5432 未映射到公网
- [ ] 能注册登录（空库需新账号）
