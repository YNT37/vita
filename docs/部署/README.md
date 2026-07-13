# Vita 部署文档索引

仓库：https://github.com/YNT37/vita

**先选一种方式，只打开对应文档即可。** SQLite 与 PostgreSQL 数据不互通，换库等于空库。

| 文档 | 适合 | 数据库 | 访问 |
|------|------|--------|------|
| [A · 本机开发](./A-本机开发-venv-SQLite.md) | 日常写代码 | SQLite | `:3000` + `:5000` |
| [B · 云服务器 venv + SQLite](./B-云服务器-venv-SQLite.md) | 考核快速演示 | SQLite | `http://IP:3000` |
| [C · 云服务器 venv + PostgreSQL](./C-云服务器-venv-PostgreSQL.md) | 更稳 | Postgres | 同上 |
| [D · Docker + SQLite](./D-Docker-SQLite.md) | 不想装 Node/Python | 容器 SQLite | `http://IP/`（80） |
| [E · Docker + PostgreSQL](./E-Docker-PostgreSQL.md) | 容器化正式 | 容器 Postgres | `http://IP/`（80） |

### 公共参考

| 文档 | 内容 |
|------|------|
| [环境变量说明](./环境变量说明.md) | `backend/.env`、`deploy/.env` 逐项 |
| [数据库：SQLite 与 PostgreSQL](./数据库-SQLite与PostgreSQL.md) | 安装、建库、备份 |
| [常见问题](./常见问题.md) | CORS、SSH 断连、换库等 |

建议：先跑通 **B**，再按需升到 **C** 或 **E**。
