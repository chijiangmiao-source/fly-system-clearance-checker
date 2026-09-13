"""FastAPI 入口：POST /api/check 接收 UTF-8 JSON，返回首次越界结果。"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal, getcontext
from fractions import Fraction

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .encounter import encounter_first_contact
from .geometry import first_collision_segmented
from .validation import FieldError, HugeInt, validate, validate_encounter

getcontext().prec = 60

# CPython 默认限制整数字符串转换 ≤4300 位。此处放宽以便测试与日志等
# 附带转换；请求解析本身经 parse_int 钩子处理，不受位限影响。
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(max(sys.get_int_max_str_digits(), 100_000))

# 超过该位数的整数字面量不做精确转换（5M 位转换需分钟级），
# 以 HugeInt 惰性标记代替，由字段级校验指出其所在字段路径。
_JSON_INT_FAST_DIGITS = 4300


def _parse_json_int(s: str):
    if len(s) <= _JSON_INT_FAST_DIGITS:
        return int(s)
    return HugeInt(s)


def _reject_json_constant(value: str):
    # NaN / Infinity / -Infinity 不是合法 JSON 语法（Python json 默认放行），
    # 必须在正文层按语法错误拒绝（path 为 ""），而不能落到字段类型校验。
    raise ValueError(f"non-standard JSON constant: {value}")

app = FastAPI(title="Stage Fly Collision API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_EMPTY_RESULT = {
    "collides": False,
    "t": None,
    "t_display": None,
    "t_fraction": None,
    "zone_id": None,
    "zone_index": None,
    "edge_index": None,
    "segment_index": None,
    "segment_t_display": None,
    "position": None,
    "position_display": None,
}


def _err(status: int, path: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"path": path, "message": message}}
    )


def _load_json_body(raw: bytes):
    """解析请求体为 Python 对象。

    成功返回 (payload, None)；失败返回 (None, JSONResponse)（沿用统一错误信封）。
    """
    if not raw:
        return None, _err(400, "", "request body is empty")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            parse_int=_parse_json_int,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError:
        return None, _err(400, "", "request body is not valid UTF-8")
    except ValueError:
        # JSON 语法错误（超长整数已由 parse_int 钩子绕过位限，不会走到这里）
        return None, _err(400, "", "request body is not valid JSON")
    return payload, None


def _frac_decimal(t: Fraction) -> Decimal:
    return Decimal(t.numerator) / Decimal(t.denominator)


def _t_display(t: Fraction) -> str:
    """最小 t 的展示值：十进制 half-up 保留六位。"""
    return str(_frac_decimal(t).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _coord_display(f: Fraction) -> str:
    """毫米坐标展示值：half-up 六位后去掉多余的尾零。"""
    q = _frac_decimal(f).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return format(q.normalize(), "f")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/check")
async def check(request: Request):
    raw = await request.body()
    payload, bad = _load_json_body(raw)
    if bad is not None:
        return bad

    try:
        data = validate(payload)
    except FieldError as e:
        return _err(400, e.path, e.message)

    result = first_collision_segmented(data["fly"], data["zones"])
    if result is None:
        return _EMPTY_RESULT

    t, segment_index, local_t, zone_id, edge_index, zone_index = result
    fly = data["fly"]
    route = [fly["start"], *(fly.get("waypoints") or []), fly["end"]]
    p0 = route[segment_index]
    p1 = route[segment_index + 1]
    px = p0["x"] + local_t * (p1["x"] - p0["x"])
    py = p0["y"] + local_t * (p1["y"] - p0["y"])
    return {
        "collides": True,
        "t": float(t),
        "t_display": _t_display(t),
        "t_fraction": f"{t.numerator}/{t.denominator}",
        "zone_id": zone_id,
        "zone_index": zone_index,
        "edge_index": edge_index,
        "segment_index": segment_index,
        "segment_t_display": _t_display(local_t),
        "position": {"x": float(px), "y": float(py)},
        "position_display": {"x": _coord_display(px), "y": _coord_display(py)},
    }


_ENCOUNTER_EMPTY_RESULT = {
    "collides": False,
    "t": None,
    "t_display": None,
    "t_fraction": None,
    "fly_a": None,
    "fly_b": None,
    "contact": None,
    "contact_display": None,
}


def _encounter_pose(fly_id, segment_index, local_t, pos) -> dict:
    px, py = pos
    return {
        "id": fly_id,
        "segment_index": segment_index,
        "segment_t_display": _t_display(local_t),
        "position": {"x": float(px), "y": float(py)},
        "position_display": {"x": _coord_display(px), "y": _coord_display(py)},
    }


@app.post("/api/encounter")
async def encounter(request: Request):
    """双吊景交会检测：两套吊景在同一总时长内等时运行的首次接触。"""
    raw = await request.body()
    payload, bad = _load_json_body(raw)
    if bad is not None:
        return bad

    try:
        data = validate_encounter(payload)
    except FieldError as e:
        return _err(400, e.path, e.message)

    result = encounter_first_contact(data["fly_a"], data["fly_b"])
    if result is None:
        return _ENCOUNTER_EMPTY_RESULT

    t, ia, ua, ib, ub, (pos_a, pos_b, contact) = result
    return {
        "collides": True,
        "t": float(t),
        "t_display": _t_display(t),
        "t_fraction": f"{t.numerator}/{t.denominator}",
        "fly_a": _encounter_pose(data["fly_a"]["id"], ia, ua, pos_a),
        "fly_b": _encounter_pose(data["fly_b"]["id"], ib, ub, pos_b),
        "contact": {"x": float(contact[0]), "y": float(contact[1])},
        "contact_display": {
            "x": _coord_display(contact[0]),
            "y": _coord_display(contact[1]),
        },
    }
