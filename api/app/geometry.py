"""连续扫掠碰撞检测。

吊景（轴对齐矩形）以左下角为基准沿直线匀速平移（不旋转），t∈[0,1]；
禁入区为静态简单多边形。边界接触与内部重叠均计为碰撞。
禁入区可选填 active_window（全程百万分之一刻度的起止整数）限定启用时段：
各段接触区间与启用窗口换算到同一时间轴后，仅在闭区间重叠（含端点相触）
时计碰撞，最早碰撞时刻为 max(首触时刻, 窗口起点)；省略时视为全程生效。

全部坐标为整数，时刻 t 用 Fraction 精确表示，比较与取舍均无浮点误差。

首次接触的事件模型（纯平移、相对姿态固定）：
  * t>0 的首次接触必为“顶点—边”事件：矩形角点落在多边形边上，
    或多边形顶点落在矩形边上（平行共线时退化为区间首端点）。
  * t=0 时可能已然相交，需要额外的静态判定：
    边—边相交（含跨穿）、矩形严格含于多边形、多边形严格含于矩形。
  * 接触时刻集：矩形与单条多边形边均为凸形，其接触时刻集为单个闭区间，
    由各顶点-边事件接触子区间的首尾端点合成（t=0 / t=1 的跨穿由静态判定补足）。
    禁入区（可非凸）的接触时刻集是各边区间的并，再加上无边界接触空隙中
    纯包含（矩形严格含于多边形 / 多边形严格含于矩形）的时段；
    U 形空腔等不接触间隙不会被并入。
"""

from __future__ import annotations

from fractions import Fraction
from typing import Optional, Sequence, Tuple

Point = Tuple[int, int]

_ZERO = Fraction(0)
_ONE = Fraction(1)

# 禁入区启用窗口（active_window）的刻度：全程 t∈[0,1] 均分为一百万份，
# 窗口以该刻度的起止整数描述（0 ≤ start_tick ≤ end_tick ≤ WINDOW_TICKS）。
WINDOW_TICKS = 1_000_000


def _cross(ux: int, uy: int, vx: int, vy: int) -> int:
    return ux * vy - uy * vx


def point_segment_contact_interval(
    p0: Point, v: Point, a: Point, b: Point
) -> Optional[Tuple[Fraction, Fraction]]:
    """动点 p0 + t·v 与闭线段 ab 的接触区间 [t_lo, t_hi]（限 t∈[0,1]），无则 None。"""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    rx = p0[0] - a[0]
    ry = p0[1] - a[1]
    c0 = _cross(dx, dy, rx, ry)  # cross(b-a, p0-a)
    cv = _cross(dx, dy, v[0], v[1])  # cross(b-a, v)
    if cv != 0:
        t = Fraction(-c0, cv)
        if t < 0 or t > 1:
            return None
        # 已共线，检查是否落在闭线段范围内：s = dot(p-a, d) / dot(d,d) ∈ [0,1]
        dd = dx * dx + dy * dy
        s_num = (rx + t * v[0]) * dx + (ry + t * v[1]) * dy
        if _ZERO <= s_num <= dd:
            return (t, t)
        return None
    if c0 != 0:
        return None  # 永不共线
    # 共线：点沿线段所在直线滑动，接触区间为参数 s∈[0,1] 对应的 t 闭区间
    dd = dx * dx + dy * dy
    s0 = rx * dx + ry * dy  # dot(p0-a, d)
    sv = v[0] * dx + v[1] * dy  # dot(v, d)
    if sv == 0:
        return (_ZERO, _ONE) if 0 <= s0 <= dd else None
    t0 = Fraction(-s0, sv)
    t1 = Fraction(dd - s0, sv)
    lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
    lo = max(lo, _ZERO)
    hi = min(hi, _ONE)
    if lo > hi:
        return None
    return (lo, hi)


def point_segment_first_t(
    p0: Point, v: Point, a: Point, b: Point
) -> Optional[Fraction]:
    """动点 p0 + t·v 首次落在闭线段 ab 上的时刻（t∈[0,1]），无则返回 None。"""
    iv = point_segment_contact_interval(p0, v, a, b)
    return iv[0] if iv is not None else None


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """闭线段 p1p2 与 p3p4 是否相交（含端点接触与共线重叠），精确整数判定。"""

    def orient(a: Point, b: Point, c: Point) -> int:
        return _cross(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1])

    d1 = orient(p3, p4, p1)
    d2 = orient(p3, p4, p2)
    d3 = orient(p1, p2, p3)
    d4 = orient(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True

    def on_seg(a: Point, b: Point, c: Point) -> bool:
        return (
            min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
        )

    if d1 == 0 and on_seg(p3, p4, p1):
        return True
    if d2 == 0 and on_seg(p3, p4, p2):
        return True
    if d3 == 0 and on_seg(p1, p2, p3):
        return True
    if d4 == 0 and on_seg(p1, p2, p4):
        return True
    return False


def point_strictly_in_polygon(p: Point, verts: Sequence[Point]) -> bool:
    """射线法严格内部判定；位于边界上返回 False。"""
    n = len(verts)
    x, y = p
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        if (
            _cross(b[0] - a[0], b[1] - a[1], x - a[0], y - a[1]) == 0
            and min(a[0], b[0]) <= x <= max(a[0], b[0])
            and min(a[1], b[1]) <= y <= max(a[1], b[1])
        ):
            return False
    inside = False
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            # 交点横坐标 xint = a.x + (y-a.y)*(b.x-a.x)/(b.y-a.y)，比较 x < xint
            dy = b[1] - a[1]
            lhs = (x - a[0]) * dy
            rhs = (y - a[1]) * (b[0] - a[0])
            if (dy > 0 and lhs < rhs) or (dy < 0 and lhs > rhs):
                inside = not inside
    return inside


def _point_strictly_in_rect(p: Point, start: Point, w: int, h: int) -> bool:
    return (
        start[0] < p[0] < start[0] + w
        and start[1] < p[1] < start[1] + h
    )


def _rect_local_edges(w: int, h: int) -> list[tuple[Point, Point]]:
    return [
        ((0, 0), (w, 0)),
        ((w, 0), (w, h)),
        ((w, h), (0, h)),
        ((0, h), (0, 0)),
    ]


def _edge_contact_interval(
    a: Point, b: Point, start: Point, d: Point, w: int, h: int
) -> Optional[Tuple[Fraction, Fraction]]:
    """平移矩形相对单条多边形边 (a,b) 的接触区间 [t_lo, t_hi]（t∈[0,1] 闭区间）。

    矩形与边均为凸形，接触时刻集是单个闭区间；各顶点-边事件的
    接触子区间之首尾即为其端点（t=0 / t=1 的跨穿型相交由静态判定补足端点）。
    """
    lo: Optional[Fraction] = None
    hi: Optional[Fraction] = None

    def consider(iv: Optional[Tuple[Fraction, Fraction]]) -> None:
        nonlocal lo, hi
        if iv is None:
            return
        if lo is None or iv[0] < lo:
            lo = iv[0]
        if hi is None or iv[1] > hi:
            hi = iv[1]

    # 矩形四角 vs 静态边
    for ox, oy in ((0, 0), (w, 0), (0, h), (w, h)):
        consider(
            point_segment_contact_interval((start[0] + ox, start[1] + oy), d, a, b)
        )
    # 边的两端点 vs 矩形四边（矩形系中端点以 -d 运动）
    vm = (-d[0], -d[1])
    for pt in (a, b):
        q0 = (pt[0] - start[0], pt[1] - start[1])
        for c1, c2 in _rect_local_edges(w, h):
            consider(point_segment_contact_interval(q0, vm, c1, c2))
    # t=0 已然相交的静态判定（跨穿型，顶点事件捕捉不到）
    for c1, c2 in _rect_local_edges(w, h):
        e1 = (c1[0] + start[0], c1[1] + start[1])
        e2 = (c2[0] + start[0], c2[1] + start[1])
        if segments_intersect(e1, e2, a, b):
            consider((_ZERO, _ZERO))
            break
    # t=1 仍相交的静态判定（跨穿持续至行程末端，退出事件落在 [0,1] 之外）
    end = (start[0] + d[0], start[1] + d[1])
    for c1, c2 in _rect_local_edges(w, h):
        e1 = (c1[0] + end[0], c1[1] + end[1])
        e2 = (c2[0] + end[0], c2[1] + end[1])
        if segments_intersect(e1, e2, a, b):
            consider((_ONE, _ONE))
            break
    if lo is None:
        return None
    return (lo, hi)


def zone_contact_window(
    vertices: Sequence[Point],
    start: Point,
    d: Point,
    w: int,
    h: int,
    w_lo: Fraction = _ZERO,
    w_hi: Fraction = _ONE,
) -> Optional[Tuple[Fraction, int]]:
    """单个禁入区在启用窗口内的 (首次碰撞时刻, 责任边序号)；无碰撞返回 None。

    接触时刻集是若干闭区间的并（非凸禁入区可互不相交，如 U 形空腔两侧）：
    各边接触区间的并集，加上无边界接触空隙中的纯包含段（矩形严格含于多边形 /
    多边形严格含于矩形）。启用窗口 [w_lo, w_hi] 与接触区间均为同一时间轴上的
    闭区间，仅当某段接触区间与窗口重叠（含端点相触）时才计碰撞，
    最早碰撞时刻为该段 max(区间起点, w_lo) 的最小值。
    纯包含（不接触其边）时段内的碰撞责任边规定为 0。
    """
    n = len(vertices)
    intervals = [
        _edge_contact_interval(vertices[j], vertices[(j + 1) % n], start, d, w, h)
        for j in range(n)
    ]
    # 边界接触时刻集：各边接触区间（各自精确）合并为有序不相交闭区间
    boundary: list[list[Fraction]] = []
    for lo, hi in sorted(iv for iv in intervals if iv is not None):
        if boundary and lo <= boundary[-1][1]:
            if hi > boundary[-1][1]:
                boundary[-1][1] = hi
        else:
            boundary.append([lo, hi])

    # 边界接触并集在 [0,1] 中的空隙：空隙内无边界接触，而纯包含状态只在
    # 边界接触事件处改变，故每个空隙内包含状态恒定，取中点判定即可；
    # 包含成立的空隙，其闭包整段计入接触时刻集
    def strictly_overlapping_at(u: Fraction) -> bool:
        pos = (start[0] + u * d[0], start[1] + u * d[1])
        return point_strictly_in_polygon(pos, vertices) or any(
            _point_strictly_in_rect(v, pos, w, h) for v in vertices
        )

    gaps: list[Tuple[Fraction, Fraction]] = []
    if not boundary:
        gaps.append((_ZERO, _ONE))
    else:
        if boundary[0][0] > _ZERO:
            gaps.append((_ZERO, boundary[0][0]))
        for k in range(len(boundary) - 1):
            gaps.append((boundary[k][1], boundary[k + 1][0]))
        if boundary[-1][1] < _ONE:
            gaps.append((boundary[-1][1], _ONE))

    pieces: list[Tuple[Fraction, Fraction]] = [tuple(iv) for iv in boundary]
    for g_lo, g_hi in gaps:
        if g_lo < g_hi and strictly_overlapping_at((g_lo + g_hi) / 2):
            pieces.append((g_lo, g_hi))

    # 合并为最终接触区间列（空隙闭包与相邻边界区间端点相接，一并合并）
    contact: list[list[Fraction]] = []
    for lo, hi in sorted(pieces):
        if contact and lo <= contact[-1][1]:
            if hi > contact[-1][1]:
                contact[-1][1] = hi
        else:
            contact.append([lo, hi])

    # 窗口重叠：按时间顺序取第一段与窗口重叠（闭区间，端点相触也算）的接触区间
    t: Optional[Fraction] = None
    for lo, hi in contact:
        cand = max(lo, w_lo)
        if cand <= min(hi, w_hi):
            t = cand
            break
    if t is None:
        return None
    # 责任边：t 时刻仍接触的最小边序号（顶点接触同时计入两条相邻边）；
    # 无任何边接触即纯包含，责任边规定为 0
    edge = 0
    for j, iv in enumerate(intervals):
        if iv is not None and iv[0] <= t <= iv[1]:
            edge = j
            break
    return t, edge


def zone_first_contact(
    vertices: Sequence[Point], start: Point, d: Point, w: int, h: int
) -> Optional[Tuple[Fraction, int]]:
    """单个禁入区的 (首次碰撞时刻, 责任边序号)；无碰撞返回 None。"""
    return zone_contact_window(vertices, start, d, w, h)


def _zone_window_local(
    zone: dict, seg_index: int, nseg: int
) -> Tuple[Fraction, Fraction]:
    """禁入区启用窗口换算到第 seg_index 段（共 nseg 段）的段内 t 闭区间。

    active_window 以全程百万分之一刻度的起止整数给出；段 i 的全程时刻为
    (i + 段内 t) / nseg，故段内窗口为 (nseg·tick − i·WINDOW_TICKS) / WINDOW_TICKS。
    省略 active_window 时视为全程生效（段内 [0,1] 全覆盖）。
    """
    aw = zone.get("active_window")
    if aw is None:
        return _ZERO, _ONE
    if isinstance(aw, dict):
        s, e = aw["start_tick"], aw["end_tick"]
    else:
        s, e = aw[0], aw[1]
    return (
        Fraction(nseg * s - seg_index * WINDOW_TICKS, WINDOW_TICKS),
        Fraction(nseg * e - seg_index * WINDOW_TICKS, WINDOW_TICKS),
    )


def _first_collision_in_segment(
    fly: dict, zones: Sequence[dict], seg_index: int, nseg: int
) -> Optional[Tuple[Fraction, str, int, int]]:
    """单段路线（段序 seg_index / 共 nseg 段）的首次碰撞。

    各禁入区的启用窗口先换算到段内 t，再求窗口内最早接触。
    责任对象决胜：先比较最小 t，再取 id 字典序较小的禁入区，
    再取从零开始的边序号较小者。
    """
    w = fly["width"]
    h = fly["height"]
    start = (fly["start"]["x"], fly["start"]["y"])
    end = (fly["end"]["x"], fly["end"]["y"])
    d = (end[0] - start[0], end[1] - start[1])
    best: Optional[Tuple[Fraction, str, int, int]] = None
    for zi, zone in enumerate(zones):
        vertices = [
            (v["x"], v["y"]) if isinstance(v, dict) else (v[0], v[1])
            for v in zone["vertices"]
        ]
        w_lo, w_hi = _zone_window_local(zone, seg_index, nseg)
        got = zone_contact_window(vertices, start, d, w, h, w_lo, w_hi)
        if got is None:
            continue
        cand = (got[0], zone["id"], got[1], zi)
        if best is None or cand[:3] < best[:3]:
            best = cand
    return best


def first_collision(
    fly: dict, zones: Sequence[dict]
) -> Optional[Tuple[Fraction, str, int, int]]:
    """全局首次碰撞，返回 (t, zone_id, edge_index, zone_index)。

    责任对象决胜：先比较最小 t，再取 id 字典序较小的禁入区，
    再取从零开始的边序号较小者。
    """
    return _first_collision_in_segment(fly, zones, 0, 1)


def first_collision_segmented(
    fly: dict, zones: Sequence[dict]
) -> Optional[Tuple[Fraction, int, Fraction, str, int, int]]:
    """折线路线（start → waypoints… → end）的全局首次碰撞。

    每段复用单段连续扫掠；各段等时，全程 t = (段序 + 段内 t) / 段数。
    汇总决胜：先比全程 t，再比段序 —— 折点两侧同时命中
    （前段段内 t=1 与后段段内 t=0）归前一段。

    返回 (全程 t, 段序, 段内 t, zone_id, edge_index, zone_index)；无碰撞 None。
    """
    w = fly["width"]
    h = fly["height"]
    points: list[Point] = [(fly["start"]["x"], fly["start"]["y"])]
    for wp in fly.get("waypoints") or []:
        points.append((wp["x"], wp["y"]) if isinstance(wp, dict) else wp)
    points.append((fly["end"]["x"], fly["end"]["y"]))
    n = len(points) - 1

    best: Optional[Tuple[Fraction, int, Fraction, str, int, int]] = None
    for i in range(n):
        seg = {
            "width": w,
            "height": h,
            "start": {"x": points[i][0], "y": points[i][1]},
            "end": {"x": points[i + 1][0], "y": points[i + 1][1]},
        }
        got = _first_collision_in_segment(seg, zones, i, n)
        if got is None:
            continue
        local_t, zone_id, edge_index, zone_index = got
        global_t = Fraction(i, n) + local_t / n
        cand = (global_t, i, local_t, zone_id, edge_index, zone_index)
        if best is None or cand[0] < best[0] or (
            cand[0] == best[0] and cand[1] < best[1]
        ):
            best = cand
    return best
