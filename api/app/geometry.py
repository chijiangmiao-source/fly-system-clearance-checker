"""连续扫掠碰撞检测。

吊景（轴对齐矩形）以左下角为基准沿直线匀速平移（不旋转），t∈[0,1]；
禁入区为静态简单多边形。边界接触与内部重叠均计为碰撞。

全部坐标为整数，时刻 t 用 Fraction 精确表示，比较与取舍均无浮点误差。

首次接触的事件模型（纯平移、相对姿态固定）：
  * t>0 的首次接触必为“顶点—边”事件：矩形角点落在多边形边上，
    或多边形顶点落在矩形边上（平行共线时退化为区间首端点）。
  * t=0 时可能已然相交，需要额外的静态判定：
    边—边相交（含跨穿）、矩形严格含于多边形、多边形严格含于矩形。
"""

from __future__ import annotations

from fractions import Fraction
from typing import Optional, Sequence, Tuple

Point = Tuple[int, int]

_ZERO = Fraction(0)


def _cross(ux: int, uy: int, vx: int, vy: int) -> int:
    return ux * vy - uy * vx


def point_segment_first_t(
    p0: Point, v: Point, a: Point, b: Point
) -> Optional[Fraction]:
    """动点 p0 + t·v 首次落在闭线段 ab 上的时刻（t∈[0,1]），无则返回 None。"""
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
            return t
        return None
    if c0 != 0:
        return None  # 永不共线
    # 共线：点沿线段所在直线滑动，求参数 s∈[0,1] 的进入时刻
    dd = dx * dx + dy * dy
    s0 = rx * dx + ry * dy  # dot(p0-a, d)
    sv = v[0] * dx + v[1] * dy  # dot(v, d)
    if sv == 0:
        return _ZERO if 0 <= s0 <= dd else None
    t0 = Fraction(-s0, sv)
    t1 = Fraction(dd - s0, sv)
    lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
    if hi < 0 or lo > 1:
        return None
    return max(lo, _ZERO)


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


def _edge_first_t(
    a: Point, b: Point, start: Point, d: Point, w: int, h: int
) -> Optional[Fraction]:
    """平移矩形相对单条多边形边 (a,b) 的首次接触时刻。"""
    best: Optional[Fraction] = None

    def consider(t: Optional[Fraction]) -> None:
        nonlocal best
        if t is not None and (best is None or t < best):
            best = t

    # 矩形四角 vs 静态边
    for ox, oy in ((0, 0), (w, 0), (0, h), (w, h)):
        consider(point_segment_first_t((start[0] + ox, start[1] + oy), d, a, b))
    # 边的两端点 vs 矩形四边（矩形系中端点以 -d 运动）
    vm = (-d[0], -d[1])
    for pt in (a, b):
        q0 = (pt[0] - start[0], pt[1] - start[1])
        for c1, c2 in _rect_local_edges(w, h):
            consider(point_segment_first_t(q0, vm, c1, c2))
    # t=0 已然相交的静态判定（跨穿型，顶点事件捕捉不到）
    if best is None or best > 0:
        for c1, c2 in _rect_local_edges(w, h):
            e1 = (c1[0] + start[0], c1[1] + start[1])
            e2 = (c2[0] + start[0], c2[1] + start[1])
            if segments_intersect(e1, e2, a, b):
                best = _ZERO
                break
    return best


def zone_first_contact(
    vertices: Sequence[Point], start: Point, d: Point, w: int, h: int
) -> Optional[Tuple[Fraction, int]]:
    """单个禁入区的 (首次碰撞时刻, 责任边序号)；无碰撞返回 None。"""
    n = len(vertices)
    best_t: Optional[Fraction] = None
    best_edge = 0
    for j in range(n):
        t = _edge_first_t(vertices[j], vertices[(j + 1) % n], start, d, w, h)
        if t is not None and (best_t is None or t < best_t):
            best_t = t
            best_edge = j
    if best_t != _ZERO:
        # t=0 且无边界接触时的纯包含（内部重叠）：责任边规定为 0
        if point_strictly_in_polygon(start, vertices) or any(
            _point_strictly_in_rect(v, start, w, h) for v in vertices
        ):
            best_t = _ZERO
            best_edge = 0
    if best_t is None:
        return None
    return best_t, best_edge


def first_collision(
    fly: dict, zones: Sequence[dict]
) -> Optional[Tuple[Fraction, str, int, int]]:
    """全局首次碰撞，返回 (t, zone_id, edge_index, zone_index)。

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
        got = zone_first_contact(vertices, start, d, w, h)
        if got is None:
            continue
        cand = (got[0], zone["id"], got[1], zi)
        if best is None or cand[:3] < best[:3]:
            best = cand
    return best
