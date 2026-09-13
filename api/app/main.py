"""FastAPI 入口：POST /api/check 接收 UTF-8 JSON，返回首次越界结果。"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal, getcontext
from fractions import Fraction

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .geometry import first_collision
from .validation import FieldError, validate

getcontext().prec = 60

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
    "position": None,
    "position_display": None,
}


def _err(status: int, path: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"path": path, "message": message}}
    )


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
    if not raw:
        return _err(400, "", "request body is empty")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _err(400, "", "request body is not valid UTF-8 JSON")

    try:
        data = validate(payload)
    except FieldError as e:
        return _err(400, e.path, e.message)

    result = first_collision(data["fly"], data["zones"])
    if result is None:
        return _EMPTY_RESULT

    t, zone_id, edge_index, zone_index = result
    fly = data["fly"]
    sx, sy = fly["start"]["x"], fly["start"]["y"]
    dx = fly["end"]["x"] - sx
    dy = fly["end"]["y"] - sy
    px = sx + t * dx
    py = sy + t * dy
    return {
        "collides": True,
        "t": float(t),
        "t_display": _t_display(t),
        "t_fraction": f"{t.numerator}/{t.denominator}",
        "zone_id": zone_id,
        "zone_index": zone_index,
        "edge_index": edge_index,
        "position": {"x": float(px), "y": float(py)},
        "position_display": {"x": _coord_display(px), "y": _coord_display(py)},
    }
