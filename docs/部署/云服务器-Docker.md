# 云服务器部署 · Docker

从 GitHub 拉取，用 Docker Compose 在云主机上线。  
返回 [部署索引](./README.md)。

**前置**：

- 云服务器公网 IP  
- 已安装 Docker + Compose 插件  
- 安全组 / 防火墙放行 **80**（HTTP）

---

## 1. 安装 Docker（Ubuntu 示例）

若已安装可跳过。国内访问 `get.docker.com` 常失败，**优先用 apt**：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# 若当前是 root 可直接用；普通用户需重新登录 SSH 后再执行 docker

docker version
docker compose version
```

若只有旧包名，可试：

```bash
sudo apt install -y docker-compose-plugin
# 或独立命令：
sudo apt install -y docker-compose
docker-compose version
```

> 已有 `docker version` 但提示 `unknown command: docker compose` 时，补装 `docker-compose-v2`（或 `docker-compose-plugin`）即可，不必再跑 get.docker.com。

---

## 2. 克隆仓库

```bash
git clone https://github.com/YNT37/vita.git
cd vita
```

之后更新：

```bash
cd ~/vita   # 或你的目录
./deploy/pull-and-up.sh
# 等价于：git pull && docker compose up -d --build
```

---

## 3. 配置 `backend/.env`

```bash
cp backend/.env.example backend/.env
vim backend/.env
```

**必改：**

```env
SECRET_KEY=用 openssl rand -hex 32 生成
JWT_SECRET=再生成一串，不要相同
```

**数据库（默认 SQLite）：**

```env
DATABASE_URL=
```

留空即可；compose 会把 SQLite 放到 Docker 卷 `vita_data`，重启不丢数据。

**AI（可选）：**

```env
AI_PROVIDER=openai
AI_API_KEY=你的key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
```

**CORS：** 同域反代下保持 `CORS_ORIGINS=*` 即可。

字段详解 → [环境变量](./环境变量.md)

---

## 4. 启动

```bash
docker compose up -d --build
```

验证：

```bash
curl -s http://127.0.0.1/api/health
```

浏览器：**http://你的公网IP/**  
（不要用 `:3000` / `:5000`，流量走 80，由 Caddy 转发。）

---

## 5. 运维

```bash
docker compose logs -f backend
docker compose ps
docker compose restart
docker compose down                 # 停服务，保留数据卷
```

备份 SQLite 数据卷（示例）：

```bash
docker run --rm -v vita_vita_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/vita-sqlite-$(date +%F).tgz -C /data .
```

卷名以 `docker volume ls | grep vita` 为准。

---

## 可选：云上使用 PostgreSQL

更适合长期跑、多写。步骤：

```bash
cp deploy/postgres.env.example deploy/postgres.env
vim deploy/postgres.env
# POSTGRES_USER=vita
# POSTGRES_PASSWORD=强密码
# POSTGRES_DB=vita

vim backend/.env
# DATABASE_URL=postgresql://vita:强密码@db:5432/vita
# 密码必须与 POSTGRES_PASSWORD 一致；主机名必须是 db
```

启动（**不要**再跑默认的 `docker-compose.yml`，避免两套抢端口）：

```bash
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env up -d --build
curl -s http://127.0.0.1/api/health
```

更新：

```bash
git pull origin main
docker compose -f docker-compose.postgres.yml --env-file deploy/postgres.env up -d --build
```

说明见 [数据库](./数据库.md)。从 SQLite 换过来**不会**自动迁数据，需重新注册。

---

## SSH 易断连

与 Docker 无关，本机配置保活：

```
# ~/.ssh/config
Host *
  ServerAliveInterval 30
  ServerAliveCountMax 6
```

---

## 检查清单

- [ ] 安全组放行 **80**
- [ ] `SECRET_KEY` / `JWT_SECRET` 已改为随机串
- [ ] `curl http://127.0.0.1/api/health` 正常
- [ ] 公网浏览器能打开并注册登录
- [ ]（可选）AI Key 已配

更多问题 → [常见问题](./常见问题.md)
