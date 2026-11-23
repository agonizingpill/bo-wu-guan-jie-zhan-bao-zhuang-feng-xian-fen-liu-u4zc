# 博物馆借展包装风险分流

栖川市博物馆藏品登记室用这本台账核对借展木箱、排定装卸窗口，处理需文保人员开箱复核的批次，并给车队留一份派车凭据。

## 工作场景

栖川市博物馆是一个虚构的地方博物馆，有 3 名藏品登记与展务人员，临展周每天处理约 8 件馆际借品。出借馆用《馆际交接单.xlsx》提供借品、包装方式及到馆期限，经办从箱签和温湿度交接单抄录现场数据，展厅另用排班表记录布置。三个问题会拖延到馆交接。

- 木箱和封签散落在不同附件里，换箱或重封后难以确认车队拿到的是哪个版本。
- 布置排班与车辆日历分别维护，纸本展厅做轨道灯标定时也可能被排入装卸。
- 高风险批次的开箱结果靠聊天记录传递，主管改判的依据和补做的抽检容易漏记。

本项目接管借展登记、包装检查、窗口排程、风险分流、复核和派车记录。上游是出借馆和收货经办，下游是读取放行状态的展务人员与馆方车队。

| 岗位 | 账号 | 页面和权限 |
| --- | --- | --- |
| 借展经办 | `operator` | 登记借展、补录包装与封签、排运输窗口、提交分流、签署开箱见证、抽检、派车 |
| 文保主管 | `supervisor` | 登记展厅布置，签署改判或暂缓，整改后重开复核。可调阅其余档案 |
| 展务阅览 | `viewer` | 只读调阅借展、排程、评分和复核档案 |

三个演示账号使用密码 `MuseumDemo!26`。登录页的演示岗位按钮会代填相应凭据。

## 一天的操作剧本

以 2026 年 11 月 26 日（上海时间）为例。

1. 08:40，经办依据《馆际交接单.xlsx》核对三件借品。`BR-2611-014` 青花缠枝莲纹瓷瓶须在 17:30 前抵达一号临展厅。
2. 09:00，经办登记瓷瓶 `BX-014`，记录泡棉贴合、山地运输、最高相对湿度 79% 和 4 次转运，实见封签 `SEAL-2611-014`。
3. 09:15，高风险瓷瓶生成开箱复核单。经办见证并记录器口、肩部和内衬情况。
4. 09:28，主管签字，说明器物由独立悬托固定且震动痕迹仅见外箱，改判后必须继续抽检。种子数据从这一环节结束后开始。
5. 10:00，经办核对瓷瓶木箱实物封签。与记录相符后，该批次才具备放行条件。
6. 12:00 至 13:30，纸本展厅标定轨道灯。`BR-2611-019` 的 12:30 至 13:15 运输窗口与布置冲突，且 `BX-019` 缺少封签。经办补录真实封签后仍需改排到 13:30 以后。
7. 13:20，车队按瓷瓶已确认的 `沪A·藏02` 窗口接单。派车后该批次档案封存，保留开箱和改判记录。
8. 13:45，`BR-2611-023` 饕餮纹青铜爵由 `沪A·藏06` 直达，低风险且封签及窗口有效，经办可直接确认派车。

## 启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

| 入口 | 地址 |
| --- | --- |
| 档案工作台 | `http://localhost:18260` |
| FastAPI / OpenAPI | `http://localhost:19260/docs` |
| PostgreSQL | `localhost:17760`，库及用户 `museum` |

演示环境退出后用 `docker compose down` 保留数据。`docker compose down -v --remove-orphans` 会清空演示卷。

## 代码和运行方式

| 层 | 技术和位置 |
| --- | --- |
| 界面 | 原生 HTML、CSS、JavaScript ES modules，`frontend/src/pages/`。`components.js` 提供档案索引、标题、状态印记和留痕，`format.js` 与 `api.js` 提供格式及 HTTP 工具，`store.js` 保存当前账号与借展档案。 |
| 接口和身份 | Python 3.12、FastAPI、JWT、scrypt，`backend/src/app.py`、`security.py`、`middleware.py`。中间件统一请求编号、访问日志和服务异常。 |
| 业务和持久层 | PostgreSQL 16、psycopg。`backend/migrations/001_archive.sql` 定义领域实体，`schemas.py` 校验输入，`loans.py`、`transit.py`、`triage.py`、`reviews.py` 执行状态规则。 |
| 计算 | Redis 7 队列和独立 Python worker，`backend/src/worker.py`、`scoring.py`。 |
| 部署 | Nginx 1.27、Docker Compose 五服务。Nginx 将 `/api/` 代理到 FastAPI。PostgreSQL 和 Redis 各有持久卷，后端与 worker 另有共享产物卷。模型留档实际写入 PostgreSQL。 |

仅调试 Python 时，可用 Compose 启动 `db`、`redis`，把 Redis 临时通过 Compose override 映射到本机，然后在 `backend/` 安装 `requirements.txt`，设置 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`，分别运行 `python -m src.startup` 与 `python -m src.worker`。开发界面可通过 `docker compose up -d --build frontend` 重建。

`.env` 可设置 `COMPOSE_PROJECT_NAME`、`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT`、`POSTGRES_PASSWORD`、`JWT_SECRET` 和 `SEED_DEMO`。启用 `SEED_DEMO` 时启动后端会按单号、用户名和布置时段创建样例，现有记录保留其当前值。共享环境应自行设置凭据，并关闭演示账号自动初始化。

## 模型和派车口径

- 输入为材质、包装结构、路线类别、最高相对湿度和转运次数。检查保存后，经办可提交分流，形成输入快照。结果入档后，只有封签可补录，通过抽检后的封签也会冻结。
- 三个类别用平滑目标编码。类别样本数为 `n` 时，编码为 `(该类别正例数 + 12 × 训练正例率) / (n + 12)`。训练行按 5 折交叉拟合，湿度和转运经标准化后，与编码一起输入 L2 LogisticRegression（`C=1.0`）。
- 用种子 `2611` 生成 960 条合成检查，分层留出 25%。模型概率达到 `0.58` 生成一张开箱复核单。留出集 ROC AUC、Brier 分数、版本、参数、样本和输入 SHA-256、编码值随结果写库。概率只代表当前演示模型的分流判断。
- PostgreSQL 保留 `queued` 状态。Redis 通知丢失时，worker 会重新推送数据库中待算的任务。计算失败保留记录并允许同一 case 重试。
- 派车同时要求封签存在、运输窗口已确认且借展已放行。同一展厅或同一车辆的有效窗口相互排斥。高风险由经办见证、主管签字，改判低风险须留理由并抽检封签。封签不符保留失败记录，仍需重新核验。

## 共享枚举

| 枚举 | 后端 | 前端 |
| --- | --- | --- |
| 岗位 | `migrations/001_archive.sql`、`schemas.py`、`security.py`、`app.py`、`scripts/seed_demo.py` | `constants.js`、`app.js` 和四个 `pages/` 模块 |
| 借展状态 | SQL 约束、`schemas.py`、`loans.py`、`transit.py`、`triage.py`、`reviews.py`、`worker.py`、seed | `constants.js`、`components.js`、`pages/archive.js`、`pages/transit.js` |
| 开箱状态 | SQL 约束、`schemas.py`、`reviews.py`、`loans.py`、`worker.py`、seed | `constants.js`、`pages/review.js`、`pages/archive.js` |
| 材质、包装、路线 | SQL 约束、`schemas.py`、`scoring.py`、seed | `constants.js`、`pages/archive.js`、`pages/triage.js` |

许可证见 [MIT License](LICENSE)。
