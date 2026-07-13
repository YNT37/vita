# 数据库：SQLite 与 PostgreSQL

返回 [部署索引](./README.md)。环境变量见 [环境变量说明](./环境变量说明.md)。

**注意**：换库不会自动迁移数据，等于空库，需重新注册。

---

## 1. SQLite（零安装，默认）

1. `backend/.env` 里 `DATABASE_URL=` **留空**。  
2. 启动后端后自动生成 `backend/vita.db`。  
3. **备份**：复制该文件。  
4. 适合：本机开发、单机演示、低并发。

用于：[A](./A-本机开发-venv-SQLite.md)、[B](./B-云服务器-venv-SQLite.md)、[D](./D-Docker-SQLite.md)。

---

## 2. 云服务器安装 PostgreSQL（Ubuntu）

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres psql
```

在 `psql` 中（替换密码）：

```sql
CREATE USER vita WITH PASSWORD '你的强密码';
CREATE DATABASE vita OWNER vita;
GRANT ALL PRIVILEGES ON DATABASE vita TO vita;
\q
```

Postgres 16+ 可能还需：

```bash
sudo -u postgres psql -d vita -c "GRANT ALL ON SCHEMA public TO vita;"
```

测试连接：

```bash
sudo systemctl restart postgresql
psql "postgresql://vita:你的强密码@127.0.0.1:5432/vita" -c 'SELECT 1;'
```

`backend/.env`：

```env
DATABASE_URL=postgresql://vita:你的强密码@127.0.0.1:5432/vita
```

**不要把 5432 对公网开放**，只本机或 Docker 内网访问。

### 备份 / 恢复

```bash
pg_dump "postgresql://vita:你的强密码@127.0.0.1:5432/vita" > vita-$(date +%F).sql
psql "postgresql://vita:你的强密码@127.0.0.1:5432/vita" < vita-2026-07-13.sql
```

用于：[C](./C-云服务器-venv-PostgreSQL.md)。

---

## 3. 仅用 Docker 跑 Postgres（后端仍在宿主机 venv）

```bash
docker run -d --name vita-pg --restart unless-stopped \
  -e POSTGRES_USER=vita \
  -e POSTGRES_PASSWORD=你的强密码 \
  -e POSTGRES_DB=vita \
  -p 127.0.0.1:5432:5432 \
  -v vita_pgdata:/var/lib/postgresql/data \
  postgres:16
```

```env
DATABASE_URL=postgresql://vita:你的强密码@127.0.0.1:5432/vita
```

也可用于方式 C。全容器方案见 [E](./E-Docker-PostgreSQL.md)（连接串主机名为 `db`）。
