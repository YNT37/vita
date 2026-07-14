# Vita 部署（仅 Docker）

仓库：https://github.com/YNT37/vita

部署统一用 **Docker Compose**，只有两种：

| 文档 | 场景 | 访问 |
|------|------|------|
| [本地 Docker](./本地-Docker.md) | 本机一键跑通 / 演示 | `http://localhost` |
| [云服务器 Docker](./云服务器-Docker.md) | 公网考核演示 | **https://vita.sanseven.top/** |

默认数据库为 **SQLite**（compose 数据卷）。可选升级 **PostgreSQL**：见各文档末尾，或 [数据库说明](./数据库.md)。

| 参考 | 说明 |
|------|------|
| [环境变量](./环境变量.md) | `backend/.env` 怎么填 |
| [数据库](./数据库.md) | SQLite / Postgres |
| [常见问题](./常见问题.md) | CORS、端口、SSH 等 |

> 写代码仍可用本机 venv + `npm run dev`（见仓库 README「本地运行」）。**上线 / 交付部署请只用 Docker。**
