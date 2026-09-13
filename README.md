# 舞台吊景越界彩排检测

矩形吊景沿折线升降的连续扫掠碰撞检测系统：React 前端 + FastAPI API + 一次性 verify 服务。

## 功能

- 前端上传 UTF-8 JSON（文本框粘贴或选择文件），**真实调用** `POST /api/check`。
- API 自行实现连续扫掠判定：吊景（轴对齐矩形）以左下角为基准匀速平移、不旋转，t∈[0,1]；
  边界接触与内部重叠均计为碰撞，返回**最小 t**（展示值十进制 half-up 保留六位）。
- **换景路线**：可在 `fly.waypoints` 中选填中途停位坐标数组，系统按 `start` → 各停位 → `end`
  组成顺序折线路线；未提供（或为空数组）时仍按原单段直线检测。各段等时，
  全程 t = (段序 + 段内 t) / 段数，折点两侧同时命中归前一段。
- 责任对象决胜：最小 t → 禁入区 `id` 字典序较小者 → 从零开始的边序号较小者；
  若 t=0 时矩形严格位于某禁入区内部且不接触其边，该区责任边规定为 0，再按同一规则决胜。
- 可缩放俯视图（滚轮缩放 / 拖拽平移）：起终与各停位姿态、完整折线路径、首次碰撞姿态、
  毫米坐标、命中段号与责任边；绿/红路段按首次命中位置分隔，无碰撞时路径全绿。
- 缺字段、非整数、越界、自交、退化、停位越界、相邻停位重复：返回 **400 + 首个错误字段路径**
  （如 `fly.start.x`、`fly.waypoints.0.x`、`zones.0.vertices`），前端保留本次原文并清除旧图。
  越界与相邻重复等语义判定严格按路线顺序 `start` → 各停位 → `end` 遍历，
  故终点与停位同时越界时先指出路线上更早的停位。
- 请求体不是合法 JSON 语法（含 `NaN` / `Infinity` / `-Infinity` 等非标准数值常量）时，
  返回 **400 + 空路径**（`path: ""`）在正文层拒绝，而非字段类型错误。
- 文件上传按 **fatal UTF-8** 解码：文件含任何非法 UTF-8 字节时页面直接拒绝并提示，
  不做替换字符（U+FFFD）处理，也不会带着损坏内容继续检测；文本框粘贴仍以原文提交。

## 输入格式

```json
{
  "stage": { "width": 10000, "height": 10000 },
  "fly": {
    "width": 1000, "height": 1000,
    "start": { "x": 0, "y": 500 },
    "waypoints": [ { "x": 5000, "y": 500 } ],
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
  （`0 ≤ x`、`x + width ≤ 10000`、`0 ≤ y`、`y + height ≤ 10000`，起点、终点与每个停位均检查）；
- `fly.waypoints` 选填；须为坐标对象数组，停位坐标为台口内整数，
  相邻点（含与 `start`、`end` 连接处）不得重复，错误定位到具体下标与坐标；
- `zones[].id` 为字符串；`zones[].vertices` 至少 3 点，按输入顺序连边（末点与首点闭合），
  面积非零且不自交（含顶点重合、边跨穿、共线回折），顶点坐标须在台口内。

## API

### `POST /api/check`

请求体即上述 JSON（UTF-8）。

**成功 200**（碰撞时）：

```json
{
  "collides": true,
  "t": 0.625,
  "t_display": "0.625000",
  "t_fraction": "5/8",
  "zone_id": "A",
  "zone_index": 0,
  "edge_index": 2,
  "segment_index": 1,
  "segment_t_display": "0.250000",
  "position": { "x": 6000.0, "y": 3000.0 },
  "position_display": { "x": "6000", "y": "3000" }
}
```

无碰撞时 `collides: false`，其余字段为 `null`。

多段路线字段：

- `t` / `t_display` / `t_fraction`：**全程等时**首次碰撞时刻——各段耗时相等，
  `t = (segment_index + 段内 t) / 段数`；
- `segment_index`：命中段序号（从 0 起，段 i 为第 i 个停位间隔）；
- `segment_t_display`：命中段内 t 的展示值（half-up 六位）；
- `position` / `position_display`：命中段几何位置（段起点 + 段内 t·段向量）。

**单段兼容**：不含 `waypoints`（或 `waypoints: []`）时 `segment_index` 恒为 `0`，
`segment_t_display` 与 `t_display` 相同，`t`、`position` 等原字段含义与数值完全不变。

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
- 折线路线逐段复用上述单段扫掠：以（全程等时 t、段序）汇总，段序小者优先
  —— 折点两侧同时命中（前段 t=1 与后段 t=0）时归前一段。

## 运行（Docker Compose）

```bash
docker compose up --build          # Web: http://localhost:8080  API: http://localhost:8000
WEB_PORT=9090 API_PORT=9000 docker compose up --build   # 覆盖宿主端口
docker compose run --rm verify     # 或 up 后单独执行一次性联调校验
```

- `web`：nginx 托管前端静态文件，并将 `/api` 反向代理到 `api:8000`；
- `api`：uvicorn 运行 FastAPI；
- `verify`：一次性服务，等待 API 健康后执行碰撞/无碰撞/缺字段/自交/超长整数/
  折线分段（第二段命中、折点归前段、多段安全、停位越界与重复、单段不回归）/Web 页面断言，
  全部通过退出码 0。

## 本地开发与测试

```bash
# API（Python 3.11）
cd api && pip install -r requirements-dev.txt
python -m pytest tests/ -q                 # 96 个用例：临界值、责任决胜、校验路径、折线分段
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
│   ├── src/                # App、StageView（可缩放折线俯视图）、lib（format/api/route）
│   ├── e2e/                # Playwright 联调
│   └── nginx.conf
├── verify/                 # 一次性联调校验服务
└── samples/                # 示例载荷
```
