# 舞台吊景越界彩排检测

矩形吊景沿直线升降的连续扫掠碰撞检测系统：React 前端 + FastAPI API + 一次性 verify 服务。

## 功能

- 前端上传 UTF-8 JSON（文本框粘贴或选择文件），**真实调用** `POST /api/check`。
- API 自行实现连续扫掠判定：吊景（轴对齐矩形）以左下角为基准匀速平移、不旋转，t∈[0,1]；
  边界接触与内部重叠均计为碰撞，返回**最小 t**（展示值十进制 half-up 保留六位）。
- 责任对象决胜：最小 t → 禁入区 `id` 字典序较小者 → 从零开始的边序号较小者；
  若 t=0 时矩形严格位于某禁入区内部且不接触其边，该区责任边规定为 0，再按同一规则决胜。
- 可缩放俯视图（滚轮缩放 / 拖拽平移）：起终姿态、完整路径、首次碰撞姿态、毫米坐标与责任边；
  无碰撞时路径全绿。
- 缺字段、非整数、越界、自交、退化：返回 **400 + 首个错误字段路径**（如 `fly.start.x`、
  `zones.0.vertices`），前端保留本次原文并清除旧图。

## 输入格式

```json
{
  "stage": { "width": 10000, "height": 10000 },
  "fly": {
    "width": 1000, "height": 1000,
    "start": { "x": 0, "y": 500 },
    "end":   { "x": 9000, "y": 500 }
  },
  "zones": [
    { "id": "A", "vertices": [ {"x": 4000, "y": 0}, {"x": 6000, "y": 0},
                               {"x": 6000, "y": 2000}, {"x": 4000, "y": 2000} ] }
  ]
}
```

约束（坐标与吊景尺寸均为整数，单位 mm）：

- `stage.width` / `stage.height` 固定为 `10000`；
- `fly.width` / `fly.height` 为正整数，且运动全程位于台口内
  （`0 ≤ x`、`x + width ≤ 10000`、`0 ≤ y`、`y + height ≤ 10000`，起终点均检查）；
- `zones[].id` 为字符串；`zones[].vertices` 至少 3 点，按输入顺序连边（末点与首点闭合），
  面积非零且不自交（含顶点重合、边跨穿、共线回折），顶点坐标须在台口内。

## API

### `POST /api/check`

请求体即上述 JSON（UTF-8）。

**成功 200**（碰撞时）：

```json
{
  "collides": true,
  "t": 0.3333333333333333,
  "t_display": "0.333333",
  "t_fraction": "1/3",
  "zone_id": "A",
  "zone_index": 0,
  "edge_index": 3,
  "position": { "x": 3000.0, "y": 500.0 },
  "position_display": { "x": "3000", "y": "500" }
}
```

无碰撞时 `collides: false`，其余字段为 `null`。

**校验失败 400**：

```json
{ "error": { "path": "fly.start.x", "message": "must be an integer" } }
```

`path` 为按文档顺序遍历得到的**首个**错误字段路径（点号 + 数组下标；JSON 语法错误为 `""`）。

另提供 `GET /api/health` 健康检查。

## 判定方法（连续扫掠，精确有理数运算）

- 纯平移、相对姿态固定 ⇒ t>0 的首次接触必为“顶点—边”事件：矩形四角 vs 多边形边、
  多边形顶点 vs 矩形四边（在矩形参考系中顶点以 −v 运动），逐对求点-线段首次接触时刻；
  共线情形退化为区间首端点。
- t=0 可能已然相交：补充边-边静态相交判定（含跨穿）与包含判定
  （矩形严格含于多边形 / 多边形严格含于矩形，责任边均为 0）。
- 全部使用整数叉积与 `Fraction` 精确计算，决胜比较无浮点误差；
  顶点接触同时计入两条相邻边，取较小边序号。

## 运行（Docker Compose）

```bash
docker compose up --build          # Web: http://localhost:8080  API: http://localhost:8000
WEB_PORT=9090 API_PORT=9000 docker compose up --build   # 覆盖宿主端口
docker compose run --rm verify     # 或 up 后单独执行一次性联调校验
```

- `web`：nginx 托管前端静态文件，并将 `/api` 反向代理到 `api:8000`；
- `api`：uvicorn 运行 FastAPI；
- `verify`：一次性服务，等待 API 健康后执行碰撞/无碰撞/缺字段/自交/Web 页面断言，
  全部通过退出码 0。

## 本地开发与测试

```bash
# API（Python 3.11）
cd api && pip install -r requirements-dev.txt
python -m pytest tests/ -q                 # 62 个用例：临界值、责任决胜、校验路径
python -m uvicorn app.main:app --port 8000

# 前端（Node 20）
cd web && npm install
npm run test                               # Vitest：half-up 舍入、API 客户端
npm run dev                                # 开发服务器（/api 代理到 localhost:8000）

# Playwright 联调（自动拉起 API 与前端）
cd web && npx playwright install chromium && npx playwright test
```

## 目录结构

```
├── docker-compose.yml      # web / api / verify 编排，WEB_PORT、API_PORT 可覆盖
├── api/                    # FastAPI：几何扫掠 + 校验 + 测试
│   ├── app/{main,geometry,validation}.py
│   └── tests/              # pytest
├── web/                    # React + Vite + TS
│   ├── src/                # App、StageView（可缩放俯视图）、lib（format/api）
│   ├── e2e/                # Playwright 联调
│   └── nginx.conf
├── verify/                 # 一次性联调校验服务
└── samples/                # 示例载荷
```
