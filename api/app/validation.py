"""请求体验证。

缺字段、非整数、越界、自交、退化 —— 一律抛出 FieldError，
携带按文档顺序遍历得到的首个错误的字段路径（点号 + 数组下标）。
"""

from __future__ import annotations

from .geometry import segments_intersect

STAGE_SIZE = 10000

_MISSING = object()


class HugeInt:
    """超过位限的整数字面量的惰性标记。

    它仍是整数（JSON 中就是整数字面量），但不做昂贵的精确转换；
    比较时视为同号无穷大 —— 任何合法取值范围都不包含它，
    因此一定会在首个字段校验处被拦截并指出字段路径。
    """

    __slots__ = ("negative",)

    def __init__(self, digits: str):
        self.negative = digits.startswith("-")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HugeInt) and self.negative == other.negative

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        return self.negative

    def __le__(self, other: object) -> bool:
        return self.negative

    def __gt__(self, other: object) -> bool:
        return not self.negative

    def __ge__(self, other: object) -> bool:
        return not self.negative

    def __add__(self, other: object) -> "HugeInt":
        return self

    __radd__ = __add__

    def __sub__(self, other: object) -> "HugeInt":
        return self

    def __rsub__(self, other: object) -> "HugeInt":
        return HugeInt("-" if not self.negative else "")

    def __hash__(self) -> int:
        return hash(("HugeInt", self.negative))


class FieldError(Exception):
    def __init__(self, path: str, message: str):
        super().__init__(message)
        self.path = path
        self.message = message


def _is_int(v: object) -> bool:
    # JSON true/false 在 Python 中是 bool（int 子类），必须排除；
    # HugeInt 是超长整数字面量的标记，同样属于整数
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, HugeInt))


def _required(obj: dict, key: str, path: str):
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        raise FieldError(path, "missing required field")
    return v


def _int_field(obj: dict, key: str, path: str) -> int:
    v = _required(obj, key, path)
    if not _is_int(v):
        raise FieldError(path, "must be an integer")
    return v


def _object_field(obj: dict, key: str, path: str) -> dict:
    v = _required(obj, key, path)
    if not isinstance(v, dict):
        raise FieldError(path, "must be an object")
    return v


def _as_object(v: object, path: str) -> dict:
    """与 _object_field 相同的对象判定，但直接接受值（用于路线逐点校验）。"""
    if v is _MISSING:
        raise FieldError(path, "missing required field")
    if not isinstance(v, dict):
        raise FieldError(path, "must be an object")
    return v


def _validate_polygon(pts: list[tuple[int, int]], path: str) -> None:
    n = len(pts)
    # 零长边（含首尾重复导致的闭合退化边）
    for i in range(n):
        if pts[i] == pts[(i + 1) % n]:
            raise FieldError(path, "degenerate polygon: zero-length edge")
    # 相邻边共线回折（边界自叠）
    for i in range(n):
        prev = pts[i - 1]
        cur = pts[i]
        nxt = pts[(i + 1) % n]
        ux, uy = prev[0] - cur[0], prev[1] - cur[1]
        vx, vy = nxt[0] - cur[0], nxt[1] - cur[1]
        if ux * vy - uy * vx == 0 and ux * vx + uy * vy > 0:
            raise FieldError(path, "self-intersecting polygon")
    # 非相邻边相交（含触碰、顶点重合、共线重叠）
    for i in range(n):
        a1, a2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # 相邻边共享端点属正常
            b1, b2 = pts[j], pts[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2):
                raise FieldError(path, "self-intersecting polygon")
    # 面积非零（有向面积为零的退化形，如共线多边形）
    area2 = 0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area2 += x1 * y2 - x2 * y1
    if area2 == 0:
        raise FieldError(path, "degenerate polygon: zero area")


def validate(payload: object) -> dict:
    """校验并返回规范化数据；首个错误以 FieldError 抛出。"""
    if not isinstance(payload, dict):
        raise FieldError("", "root must be a JSON object")

    stage = _object_field(payload, "stage", "stage")
    for key in ("width", "height"):
        v = _int_field(stage, key, f"stage.{key}")
        if v != STAGE_SIZE:
            raise FieldError(f"stage.{key}", f"must equal {STAGE_SIZE}")

    fly = _object_field(payload, "fly", "fly")
    fw = _int_field(fly, "width", "fly.width")
    if fw < 1:
        raise FieldError("fly.width", "must be a positive integer")
    fh = _int_field(fly, "height", "fly.height")
    if fh < 1:
        raise FieldError("fly.height", "must be a positive integer")

    def _check_point(v: object, path: str) -> dict:
        # 单个路线点：结构 → 类型 → 台口越界，x 先于 y，
        # 使调用方严格按路线顺序逐点校验时首个错误定位正确
        pt = _as_object(v, path)
        x = _int_field(pt, "x", f"{path}.x")
        if x < 0 or x + fw > STAGE_SIZE:
            raise FieldError(f"{path}.x", "fly must stay within the stage")
        y = _int_field(pt, "y", f"{path}.y")
        if y < 0 or y + fh > STAGE_SIZE:
            raise FieldError(f"{path}.y", "fly must stay within the stage")
        return {"x": x, "y": y}

    # 严格按路线顺序 start → 各停位 → end 逐点校验（每点结构、类型、越界一并完成）：
    # 起点越界必须先于后续停位/终点的任何错误；停位又先于终点。
    start = _check_point(fly.get("start", _MISSING), "fly.start")

    # 可选中途停位：按 start → 各停位 → end 组成折线路线
    waypoints: list[dict] | None = None
    if "waypoints" in fly:
        wps_raw = fly["waypoints"]
        if not isinstance(wps_raw, list):
            raise FieldError("fly.waypoints", "must be an array")
        waypoints = []
        prev = start
        for i, wp_raw in enumerate(wps_raw):
            wpath = f"fly.waypoints.{i}"
            pt = _check_point(wp_raw, wpath)
            # 相邻重复点（含与起点重合），错误定位到后一个停位的下标
            if pt == prev:
                raise FieldError(
                    wpath, f"duplicate adjacent waypoint at ({pt['x']}, {pt['y']})"
                )
            waypoints.append(pt)
            prev = pt

    end = _check_point(fly.get("end", _MISSING), "fly.end")
    # 末停位与终点重合：错误位置在末停位（路线上早于终点），仍定位到该停位下标
    if waypoints and waypoints[-1] == end:
        x = waypoints[-1]["x"]
        y = waypoints[-1]["y"]
        k = len(waypoints) - 1
        raise FieldError(
            f"fly.waypoints.{k}", f"duplicate adjacent waypoint at ({x}, {y})"
        )

    zones_raw = _required(payload, "zones", "zones")
    if not isinstance(zones_raw, list):
        raise FieldError("zones", "must be an array")
    zones = []
    for i, zone in enumerate(zones_raw):
        zpath = f"zones.{i}"
        if not isinstance(zone, dict):
            raise FieldError(zpath, "must be an object")
        zid = _required(zone, "id", f"{zpath}.id")
        if not isinstance(zid, str):
            raise FieldError(f"{zpath}.id", "must be a string")
        verts_raw = _required(zone, "vertices", f"{zpath}.vertices")
        if not isinstance(verts_raw, list):
            raise FieldError(f"{zpath}.vertices", "must be an array")
        if len(verts_raw) < 3:
            raise FieldError(f"{zpath}.vertices", "needs at least 3 vertices")
        pts: list[tuple[int, int]] = []
        for j, vtx in enumerate(verts_raw):
            vpath = f"{zpath}.vertices.{j}"
            if not isinstance(vtx, dict):
                raise FieldError(vpath, "must be an object")
            x = _int_field(vtx, "x", f"{vpath}.x")
            if not 0 <= x <= STAGE_SIZE:
                raise FieldError(f"{vpath}.x", "coordinate out of stage bounds")
            y = _int_field(vtx, "y", f"{vpath}.y")
            if not 0 <= y <= STAGE_SIZE:
                raise FieldError(f"{vpath}.y", "coordinate out of stage bounds")
            pts.append((x, y))
        _validate_polygon(pts, f"{zpath}.vertices")
        zones.append({"id": zid, "vertices": pts})

    return {
        "stage": {"width": STAGE_SIZE, "height": STAGE_SIZE},
        "fly": {
            "width": fw,
            "height": fh,
            "start": start,
            "end": end,
            "waypoints": waypoints,
        },
        "zones": zones,
    }
