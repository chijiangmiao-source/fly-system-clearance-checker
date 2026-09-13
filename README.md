# 舞台吊景越界彩排检测

矩形吊景沿折线升降的连续扫掠碰撞检测系统：React 前端 + FastAPI API + 一次性 verify 服务。
另含**独立的双吊景交会分析模块**（`POST /api/encounter`）：两套编号不同的吊景在同一总时长内
等时运行，精确求两矩形的全程首次接触。

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
  各路线点按顺序逐点校验（结构、类型、越界在同一点内一并完成，x 先于 y），
  故起点越界先于后续停位/终点的任何错误，停位又先于终点。
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

## 双吊景交会分析（`POST /api/encounter`）

换景时两套吊景同步运行：以**编号不同的两套吊景及各自折线路线**组成交会方案，各自所有分段
在**同一总时长** t∈[0,1] 内等时运行（段内匀速）。服务端按双方折点时刻 `i/n`、`j/m` 的并集
切分共同时间轴，用**精确有理数**（`Fraction`）计算两个轴对齐矩形的首次接触；**边界接触也算
冲突**。输入仍沿用台口尺寸与折线坐标规则，但无 `zones`。

```json
{
  "stage": { "width": 10000, "height": 10000 },
  "fly_a": {
    "id": "A", "width": 1000, "height": 1000,
    "start": { "x": 0, "y": 3000 },
    "waypoints": [ { "x": 5000, "y": 3000 } ],
    "end": { "x": 9000, "y": 3000 }
  },
  "fly_b": {
    "id": "B", "width": 1000, "height": 1000,
    "start": { "x": 9000, "y": 2000 },
    "waypoints": [ { "x": 6000, "y": 4000 }, { "x": 3000, "y": 4000 } ],
    "end": { "x": 0, "y": 2000 }
  }
}
```

- `fly_a.id` / `fly_b.id` 为非空字符串且**必须相异**（相同报 400，路径 `fly_b.id`）；
- 两套吊景的尺寸、`start` / `waypoints` / `end` 规则与单吊景完全一致（正整数尺寸、台口内
  整数坐标、相邻点不重复），字段路径分别落在 `fly_a.*`、`fly_b.*`，首个错误按
  stage → fly_a（含整条路线）→ fly_b → 编号相异的文档顺序定位；
- 双方分段数可以不同。

**成功 200**（接触时）：

```json
{
  "collides": true,
  "t": 0.42105263157894735,
  "t_display": "0.421053",
  "t_fraction": "8/19",
  "fly_a": {
    "id": "A", "segment_index": 0, "segment_t_display": "0.842105",
    "position": { "x": 4210.526315789473, "y": 3000.0 },
    "position_display": { "x": "4210.526316", "y": "3000" }
  },
  "fly_b": {
    "id": "B", "segment_index": 1, "segment_t_display": "0.263158",
    "position": { "x": 5210.526315789473, "y": 4000.0 },
    "position_display": { "x": "5210.526316", "y": "4000" }
  },
  "contact": { "x": 5210.526315789473, "y": 4000.0 },
  "contact_display": { "x": "5210.526316", "y": "4000" }
}
```

- `t` / `t_display` / `t_fraction`：全程首次接触时刻（half-up 六位）；
- `fly_a` / `fly_b`：接触瞬间该吊景所在段号（从 0 起）、段内 t 展示值与左下角坐标；
- `contact` / `contact_display`：接触位置（接触瞬间两矩形交集的中心；边/面接触时取接触面段中点）。

全程无接触时 `collides: false`，`t*`、`fly_a`、`fly_b`、`contact*` 均为 `null`。
折点两侧同时接触（前段段内 t=1 与后段段内 t=0 等价）时归前段。请求体非法 JSON / 非 UTF-8 /
字段错误同样返回 **400 + 统一错误信封**（语法错误路径为 `""`）。

页面顶部“双吊景交会分析”页签提供独立的交会方案编辑（粘贴或选文件）与检测入口：提交中、
成功、校验失败为各自独立状态；成功后在既有可缩放俯视图能力之上**同时绘制两条路线**
（各自安全段/危险段、起终与停位姿态）、双方首次接触姿态与接触点；校验失败时保留本次原文
并清除上一次结果。

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

双吊景交会（`app/encounter.py`）不涉及多边形：按双方折点时刻并集切分共同时间轴，小区间内
双方各处于固定分段，两矩形在 x、y 轴上的边界坐标均为 t 的仿射函数。每个轴向“两移动区间
相交”的时刻集是一个闭区间（相对位置 −s_b ≤ d(t) ≤ s_a，等号即接触），两轴区间相交即发生
接触，取交集左端为该小区间首次接触时刻；自左向右扫描、严格更小时替换（折点接触归前段）。
全程 `Fraction` 运算，并用 1200 组随机路线与稠密浮点采样交叉核对。

## 运行（Docker Compose）

```bash
docker compose up --build          # Web: http://localhost:8080  API: http://localhost:8000
WEB_PORT=9090 API_PORT=9000 docker compose up --build   # 覆盖宿主端口
docker compose run --rm verify     # 或 up 后单独执行一次性联调校验
```

- `web`：nginx 托管前端静态文件，并将 `/api` 反向代理到 `api:8000`；
- `api`：uvicorn 运行 FastAPI；
- `verify`：一次性服务，等待 API 健康后执行碰撞/无碰撞/缺字段/自交/超长整数/
  折线分段（第二段命中、折点归前段、多段安全、停位越界与重复、单段不回归）/
  双吊景交会（起始即接触、分段数不同中途相撞、时间错开安全、第二套越界、编号相同、原接口不回归）/
  Web 页面断言，全部通过退出码 0。

## 本地开发与测试

```bash
# API（Python 3.11）
cd api && pip install -r requirements-dev.txt
python -m pytest tests/ -q                 # 用例：临界值、责任决胜、校验路径、折线分段、双吊景交会
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
├── api/                    # FastAPI：几何扫掠 + 校验 + 双吊景交会 + 测试
│   ├── app/{main,geometry,encounter,validation}.py
│   └── tests/              # pytest
├── web/                    # React + Vite + TS
│   ├── src/                # App（页签）、StageView/EncounterView（可缩放俯视图）、StageCanvas、lib
│   ├── e2e/                # Playwright 联调
│   └── nginx.conf
├── verify/                 # 一次性联调校验服务
└── samples/                # 示例载荷
```
