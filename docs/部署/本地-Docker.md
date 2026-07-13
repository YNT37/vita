# 本地部署 · Docker

用 Docker 在本机启动完整 Vita（前端 + 后端 + Caddy，**80 端口**）。  
返回 [部署索引](./README.md)。

**前置**：已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows/macOS）或 Docker Engine + Compose（Linux）。

---

## 1. 获取代码

```bash
git clone https://github.com/YNT37/vita.git
cd vita
```

若已有仓库：`cd` 到项目根目录即可。

---

## 2. 配置 `backend/.env`

```bash
cp backend/.env.example backend/.env
```

用 vim / 记事本打开 `backend/.env`，**至少改**：

```env
SECRET_KEY=本地可随便改一串
JWT_SECRET=再改一串，不要相同
```

- `DATABASE_URL` **留空**：compose 会使用容器内 SQLite 卷（不必自己填路径）。
- AI 相关可选；不填也能登录、记账，对话为降级文案。
- 完整字段说明 → [环境变量](./环境变量.md)

---

## 3. 启动

```bash
docker compose up -d --build
```

首次会构建镜像，可能要几分钟。

---

## 4. 验证

```bash
curl -s http://127.0.0.1/api/health
# 应返回 {"status":"ok"}
```

浏览器打开：**http://localhost**  
（Caddy：`/` → 前端，`/api` → 后端，同域无需再配 `NEXT_PUBLIC_API_BASE`。）

---

## 5. 常用命令

```bash
docker compose logs -f          # 看日志
docker compose logs -f backend
docker compose restart
docker compose down             # 停止（数据卷保留）
docker compose down -v          # 停止并删除 SQLite 卷（清空数据）
```

更新代码后：

```bash
git pull
docker compose up -d --build
```

---

## 可选：本地 Docker + PostgreSQL

需要 Postgres 时用另一编排（密码两处一致）：

```bash
cp deploy/postgres.env.example deploy/postgres.env
# 编辑 POSTGRES_PASSWORD

# backend/.env 中设置：
# DATABASE_URL=postgresql://vita:同一密码@db:5432/vita

docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env up -d --build
```

详见 [数据库](./数据库.md) 与 [云服务器文档](./云服务器-Docker.md) 中的 Postgres 小节（步骤相同，只是访问仍是 localhost）。

---

## 检查清单

- [ ] Docker 已运行
- [ ] `SECRET_KEY` / `JWT_SECRET` 已改
- [ ] `http://localhost` 能注册、登录、记一笔
