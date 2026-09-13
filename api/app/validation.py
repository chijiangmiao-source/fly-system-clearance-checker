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


def validate_stage(payload: dict) -> None:
    """校验共用台口尺寸；首个错误以 FieldError 抛出。"""
    stage = _object_field(payload, "stage", "stage")
    for key in ("width", "height"):
        v = _int_field(stage, key, f"stage.{key}")
        if v != STAGE_SIZE:
            raise FieldError(f"stage.{key}", f"must equal {STAGE_SIZE}")


def _validate_duration_weights(fly: dict, prefix: str, nseg: int) -> list[int] | None:
    """校验选填的各段相对耗时（正整数数组，长度等于段数）。

    未提供时返回 None（各段等时）；长度不符定位到 duration_weights 本身，
    非整数 / 非正整数定位到具体下标。
    """
    if "duration_weights" not in fly:
        return None
    raw = fly["duration_weights"]
    path = f"{prefix}.duration_weights"
    if not isinstance(raw, list):
        raise FieldError(path, "must be an array")
    if len(raw) != nseg:
        raise FieldError(
            path, f"must have exactly {nseg} weight(s), one per route segment"
        )
    weights: list[int] = []
    for i, w in enumerate(raw):
        wpath = f"{path}.{i}"
        # 严格 int（排除 bool 与超长整数的 HugeInt 惰性标记——权重参与精确
        # 有理数运算，无法以惰性标记代替）
        if isinstance(w, bool) or not isinstance(w, int):
            raise FieldError(wpath, "must be an integer")
        if w < 1:
            raise FieldError(wpath, "must be a positive integer")
        weights.append(w)
    return weights


def validate_route_fields(
    fly: dict, prefix: str, *, with_duration_weights: bool = False
) -> dict:
    """校验单个吊景块的尺寸与折线路线（对象本身由调用方检查）。

    字段路径以 prefix 为根（单吊景为 "fly"，双吊景为 "fly_a"/"fly_b"）。
    严格按路线顺序 start → 各停位 → end 逐点校验，返回规范化路线数据。
    with_duration_weights 仅在双吊景交会方案中为真：此时按路线顺序在校完
    整条路线后校验选填的 duration_weights（长度 = 段数）。
    """
    fw = _int_field(fly, "width", f"{prefix}.width")
    if fw < 1:
        raise FieldError(f"{prefix}.width", "must be a positive integer")
    fh = _int_field(fly, "height", f"{prefix}.height")
    if fh < 1:
        raise FieldError(f"{prefix}.height", "must be a positive integer")

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
    start = _check_point(fly.get("start", _MISSING), f"{prefix}.start")

    # 可选中途停位：按 start → 各停位 → end 组成折线路线
    waypoints: list[dict] | None = None
    if "waypoints" in fly:
        wps_raw = fly["waypoints"]
        wp_path = f"{prefix}.waypoints"
        if not isinstance(wps_raw, list):
            raise FieldError(wp_path, "must be an array")
        waypoints = []
        prev = start
        for i, wp_raw in enumerate(wps_raw):
            wpath = f"{wp_path}.{i}"
            pt = _check_point(wp_raw, wpath)
            # 相邻重复点（含与起点重合），错误定位到后一个停位的下标
            if pt == prev:
                raise FieldError(
                    wpath, f"duplicate adjacent waypoint at ({pt['x']}, {pt['y']})"
                )
            waypoints.append(pt)
            prev = pt

    end = _check_point(fly.get("end", _MISSING), f"{prefix}.end")
    # 末停位与终点重合：错误位置在末停位（路线上早于终点），仍定位到该停位下标
    if waypoints and waypoints[-1] == end:
        x = waypoints[-1]["x"]
        y = waypoints[-1]["y"]
        k = len(waypoints) - 1
        raise FieldError(
            f"{prefix}.waypoints.{k}",
            f"duplicate adjacent waypoint at ({x}, {y})",
        )

    result = {
        "width": fw,
        "height": fh,
        "start": start,
        "end": end,
        "waypoints": waypoints,
    }
    if with_duration_weights:
        nseg = 1 + (len(waypoints) if waypoints else 0)
        result["duration_weights"] = _validate_duration_weights(fly, prefix, nseg)
    return result


def validate(payload: object) -> dict:
    """校验并返回规范化数据；首个错误以 FieldError 抛出。"""
    if not isinstance(payload, dict):
        raise FieldError("", "root must be a JSON object")

    validate_stage(payload)

    fly = _object_field(payload, "fly", "fly")
    fly_data = validate_route_fields(fly, "fly")

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
        "fly": fly_data,
        "zones": zones,
    }


def _validate_encounter_id(obj: dict, key: str, path: str) -> str:
    v = _required(obj, key, path)
    if not isinstance(v, str):
        raise FieldError(path, "must be a string")
    if v == "":
        raise FieldError(path, "must not be empty")
    return v


def validate_encounter(payload: object) -> dict:
    """校验双吊景交会方案；首个错误以 FieldError 抛出。

    文档顺序：stage → fly_a（id/尺寸/整条路线/选填 duration_weights）→ fly_b
    → 编号相异；错误字段路径分别落在 fly_a.* 与 fly_b.*，沿用单吊景的错误信封。
    duration_weights 为各路线段相对耗时的正整数数组（长度 = 段数），省略时各段等时。
    """
    if not isinstance(payload, dict):
        raise FieldError("", "root must be a JSON object")

    validate_stage(payload)

    fly_a_raw = _object_field(payload, "fly_a", "fly_a")
    id_a = _validate_encounter_id(fly_a_raw, "id", "fly_a.id")
    fly_a = validate_route_fields(fly_a_raw, "fly_a", with_duration_weights=True)

    fly_b_raw = _object_field(payload, "fly_b", "fly_b")
    id_b = _validate_encounter_id(fly_b_raw, "id", "fly_b.id")
    fly_b = validate_route_fields(fly_b_raw, "fly_b", with_duration_weights=True)

    if id_a == id_b:
        raise FieldError("fly_b.id", "the two flies must have distinct ids")

    return {
        "stage": {"width": STAGE_SIZE, "height": STAGE_SIZE},
        "fly_a": {"id": id_a, **fly_a},
        "fly_b": {"id": id_b, **fly_b},
    }
