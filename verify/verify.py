"""一次性联调校验：等待 API 与 Web 就绪后执行断言，全部通过则退出码 0。"""

from __future__ import annotations

import os
import sys
import time

import httpx

API = os.environ.get("API_URL", "http://api:8000").rstrip("/")
WEB = os.environ.get("WEB_URL", "http://web:80").rstrip("/")

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not cond else ""), flush=True)
    if not cond:
        FAILURES.append(name)


def wait_ready(url: str, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1.5)
    return False


def main() -> int:
    check("api healthy", wait_ready(f"{API}/api/health"))
    check("web serving", wait_ready(f"{WEB}/"))

    # 1) 碰撞：t=1/3，责任区 A，责任边 3
    collision = {
        "stage": {"width": 10000, "height": 10000},
        "fly": {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500}},
        "zones": [
            {"id": "A", "vertices": [{"x": 4000, "y": 0}, {"x": 6000, "y": 0}, {"x": 6000, "y": 2000}, {"x": 4000, "y": 2000}]}
        ],
    }
    try:
        r = httpx.post(f"{API}/api/check", json=collision, timeout=5)
        body = r.json()
        check("collision status 200", r.status_code == 200, str(r.status_code))
        check("collision t_display", body.get("t_display") == "0.333333", str(body))
        check("collision zone", body.get("zone_id") == "A", str(body))
        check("collision edge", body.get("edge_index") == 3, str(body))
        check("collision position", body.get("position_display") == {"x": "3000", "y": "500"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("collision request", False, repr(e))

    # 2) 无碰撞
    safe = {"stage": {"width": 10000, "height": 10000},
            "fly": {"width": 1000, "height": 1000, "start": {"x": 0, "y": 3000}, "end": {"x": 9000, "y": 3000}},
            "zones": collision["zones"]}
    try:
        r = httpx.post(f"{API}/api/check", json=safe, timeout=5)
        check("safe no collision", r.status_code == 200 and r.json().get("collides") is False, r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("safe request", False, repr(e))

    # 3) 缺字段 → 400 + 首个字段路径
    missing = {"stage": {"width": 10000, "height": 10000},
               "fly": {"width": 1000, "height": 1000, "start": {"y": 500}, "end": {"x": 9000, "y": 500}},
               "zones": []}
    try:
        r = httpx.post(f"{API}/api/check", json=missing, timeout=5)
        check("missing field 400", r.status_code == 400, str(r.status_code))
        check("missing field path", r.json().get("error", {}).get("path") == "fly.start.x", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("missing field request", False, repr(e))

    # 4) 自交多边形 → 400 + zones.0.vertices
    bowtie = {"stage": {"width": 10000, "height": 10000},
              "fly": {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500}},
              "zones": [{"id": "BAD", "vertices": [{"x": 0, "y": 0}, {"x": 100, "y": 100}, {"x": 100, "y": 0}, {"x": 0, "y": 100}]}]}
    try:
        r = httpx.post(f"{API}/api/check", json=bowtie, timeout=5)
        check("self-intersect 400", r.status_code == 400, str(r.status_code))
        check("self-intersect path", r.json().get("error", {}).get("path") == "zones.0.vertices", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("self-intersect request", False, repr(e))

    # 5) 超长整数（>4300 位）→ 400 + stage.width，不得 500
    big = "9" * 5000
    long_int_text = (
        '{"stage":{"width":' + big + ',"height":10000},'
        '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
        '"zones":[]}'
    )
    try:
        r = httpx.post(
            f"{API}/api/check",
            content=long_int_text.encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=5,
        )
        check("long integer 400", r.status_code == 400, str(r.status_code))
        check("long integer path", r.json().get("error", {}).get("path") == "stage.width", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("long integer request", False, repr(e))

    # 5b) 超十万位整数 → 同样精确到 stage.width（惰性解析，不得整份拒绝）
    huge = "8" * 200_000
    huge_int_text = (
        '{"stage":{"width":' + huge + ',"height":10000},'
        '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
        '"zones":[]}'
    )
    try:
        r = httpx.post(
            f"{API}/api/check",
            content=huge_int_text.encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10,
        )
        check("huge integer 400", r.status_code == 400, str(r.status_code))
        check("huge integer path", r.json().get("error", {}).get("path") == "stage.width", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("huge integer request", False, repr(e))

    # 6a) 折线路线：第二段首次碰撞稳定定位
    #    start (0,3000) → 停位 (5000,3000) → end (9000,3000)；
    #    区左缘 x=7000：第二段段内 t=1/4，全程等时 t=(1+1/4)/2=5/8，命中 (6000,3000)
    seg_zone = {"id": "A", "vertices": [
        {"x": 7000, "y": 2500}, {"x": 9000, "y": 2500},
        {"x": 9000, "y": 3500}, {"x": 7000, "y": 3500}]}
    seg2 = {"stage": {"width": 10000, "height": 10000},
            "fly": {"width": 1000, "height": 1000,
                    "start": {"x": 0, "y": 3000},
                    "waypoints": [{"x": 5000, "y": 3000}],
                    "end": {"x": 9000, "y": 3000}},
            "zones": [seg_zone]}
    try:
        r = httpx.post(f"{API}/api/check", json=seg2, timeout=5)
        body = r.json()
        check("seg2 status 200", r.status_code == 200, str(r.status_code))
        check("seg2 global t", body.get("t_fraction") == "5/8", str(body))
        check("seg2 segment_index", body.get("segment_index") == 1, str(body))
        check("seg2 segment_t_display", body.get("segment_t_display") == "0.250000", str(body))
        check("seg2 position", body.get("position_display") == {"x": "6000", "y": "3000"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("seg2 request", False, repr(e))

    # 6b) 折点两侧同时命中 → 归前段（segment_index=0，段内 t=1）
    vertex = {"stage": {"width": 10000, "height": 10000},
              "fly": {"width": 1000, "height": 1000,
                      "start": {"x": 0, "y": 0},
                      "waypoints": [{"x": 4000, "y": 4000}],
                      "end": {"x": 0, "y": 8000}},
              "zones": [{"id": "B", "vertices": [
                  {"x": 3000, "y": 5000}, {"x": 4000, "y": 5000},
                  {"x": 4000, "y": 6000}, {"x": 3000, "y": 6000}]}]}
    try:
        r = httpx.post(f"{API}/api/check", json=vertex, timeout=5)
        body = r.json()
        check("vertex status 200", r.status_code == 200, str(r.status_code))
        check("vertex earlier segment", body.get("segment_index") == 0, str(body))
        check("vertex global t half", body.get("t_fraction") == "1/2", str(body))
        check("vertex segment t one", body.get("segment_t_display") == "1.000000", str(body))
        check("vertex position", body.get("position_display") == {"x": "4000", "y": "4000"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("vertex request", False, repr(e))

    # 6c) 多段安全路线 → collides False
    multi_safe = {"stage": {"width": 10000, "height": 10000},
                  "fly": {"width": 1000, "height": 1000,
                          "start": {"x": 0, "y": 8000},
                          "waypoints": [{"x": 5000, "y": 3000}],
                          "end": {"x": 9000, "y": 8000}},
                  "zones": [seg_zone]}
    try:
        r = httpx.post(f"{API}/api/check", json=multi_safe, timeout=5)
        body = r.json()
        check("multi-safe no collision", r.status_code == 200 and body.get("collides") is False, r.text[:200])
        check("multi-safe no segment", body.get("segment_index") is None, str(body))
    except Exception as e:  # noqa: BLE001
        check("multi-safe request", False, repr(e))

    # 6d) 停位越界 → 400 + fly.waypoints.0.x
    wb = {"stage": {"width": 10000, "height": 10000},
          "fly": {"width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 0},
                  "waypoints": [{"x": 9001, "y": 0}],
                  "end": {"x": 9000, "y": 9000}},
          "zones": []}
    try:
        r = httpx.post(f"{API}/api/check", json=wb, timeout=5)
        check("waypoint oob 400", r.status_code == 400, str(r.status_code))
        check("waypoint oob path", r.json().get("error", {}).get("path") == "fly.waypoints.0.x", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("waypoint oob request", False, repr(e))

    # 6e) 相邻停位重复 → 400 + 具体下标与坐标
    wd = {"stage": {"width": 10000, "height": 10000},
          "fly": {"width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 0},
                  "waypoints": [{"x": 5000, "y": 5000}, {"x": 5000, "y": 5000}],
                  "end": {"x": 9000, "y": 9000}},
          "zones": []}
    try:
        r = httpx.post(f"{API}/api/check", json=wd, timeout=5)
        err = r.json().get("error", {})
        check("waypoint dup 400", r.status_code == 400, str(r.status_code))
        check("waypoint dup path", err.get("path") == "fly.waypoints.1", r.text[:200])
        check("waypoint dup coords", "(5000, 5000)" in err.get("message", ""), str(err))
    except Exception as e:  # noqa: BLE001
        check("waypoint dup request", False, repr(e))

    # 6f) 不含 waypoints 的既有请求不回归：新字段 segment_index=0、segment_t_display=t_display
    try:
        r = httpx.post(f"{API}/api/check", json=collision, timeout=5)
        body = r.json()
        check("legacy segment_index", body.get("segment_index") == 0, str(body))
        check("legacy segment_t_display",
              body.get("segment_t_display") == body.get("t_display") == "0.333333", str(body))
    except Exception as e:  # noqa: BLE001
        check("legacy request", False, repr(e))

    # 6g) 首个停位与终点同时越界 → 按路线顺序先报 fly.waypoints.0.x
    wbo = {"stage": {"width": 10000, "height": 10000},
           "fly": {"width": 1000, "height": 1000,
                   "start": {"x": 0, "y": 0},
                   "waypoints": [{"x": 9001, "y": 0}],
                   "end": {"x": 9001, "y": 9001}},
           "zones": []}
    try:
        r = httpx.post(f"{API}/api/check", json=wbo, timeout=5)
        err = r.json().get("error", {})
        check("waypoint-before-end oob 400", r.status_code == 400, str(r.status_code))
        check("waypoint-before-end oob path", err.get("path") == "fly.waypoints.0.x", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("waypoint-before-end oob request", False, repr(e))

    # 6h) 起点越界且后续停位格式错误 → 先报起点横坐标（每点结构/类型/越界按路线顺序逐点校验）
    sbo = {"stage": {"width": 10000, "height": 10000},
           "fly": {"width": 1000, "height": 1000,
                   "start": {"x": -1, "y": 0},
                   "waypoints": [{"x": "oops", "y": 0}],
                   "end": {"x": 9000, "y": 9000}},
           "zones": []}
    try:
        r = httpx.post(f"{API}/api/check", json=sbo, timeout=5)
        err = r.json().get("error", {})
        check("start-oob-first 400", r.status_code == 400, str(r.status_code))
        check("start-oob-first path", err.get("path") == "fly.start.x", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("start-oob-first request", False, repr(e))

    # 7a) 非标准数值常量 NaN：属非法 JSON 语法 → 400 + path ""，不得报字段类型错误
    nan_text = (
        '{"stage":{"width":10000,"height":10000},'
        '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},'
        '"waypoints":[{"x":NaN,"y":0}],"end":{"x":1000,"y":0}},'
        '"zones":[]}'
    )
    try:
        r = httpx.post(
            f"{API}/api/check",
            content=nan_text.encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=5,
        )
        err = r.json().get("error", {})
        check("NaN constant 400", r.status_code == 400, str(r.status_code))
        check("NaN constant syntax path", err.get("path") == "", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("NaN constant request", False, repr(e))

    # 7b) Infinity / -Infinity 同样按语法错误拒绝
    for const in ("Infinity", "-Infinity"):
        inf_text = nan_text.replace("NaN", const)
        try:
            r = httpx.post(
                f"{API}/api/check",
                content=inf_text.encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=5,
            )
            check(f"{const} constant syntax path",
                  r.status_code == 400 and r.json().get("error", {}).get("path") == "",
                  r.text[:200])
        except Exception as e:  # noqa: BLE001
            check(f"{const} constant request", False, repr(e))

    # 7c) 禁入区名称含非法 UTF-8 字节 → 400 + path ""，整份拒绝、不得替换字符继续
    bad_utf8 = (
        b'{"stage":{"width":10000,"height":10000},'
        b'"fly":{"width":1000,"height":1000,"start":{"x":0,"y":500},"end":{"x":1000,"y":500}},'
        b'"zones":[{"id":"A\xff","vertices":'
        b'[{"x":0,"y":0},{"x":100,"y":0},{"x":0,"y":100}]}]}'
    )
    try:
        r = httpx.post(
            f"{API}/api/check",
            content=bad_utf8,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=5,
        )
        err = r.json().get("error", {})
        check("invalid UTF-8 400", r.status_code == 400, str(r.status_code))
        check("invalid UTF-8 path", err.get("path") == "", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("invalid UTF-8 request", False, repr(e))

    # 8) 双吊景交会分析（独立模块 POST /api/encounter）
    # 8a) 起始即接触（共边，t=0 也算冲突）
    enc_start = {
        "stage": {"width": 10000, "height": 10000},
        "fly_a": {"id": "A", "width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 0}, "end": {"x": 4000, "y": 0}},
        "fly_b": {"id": "B", "width": 1000, "height": 1000,
                  "start": {"x": 1000, "y": 0}, "end": {"x": 5000, "y": 0}},
    }
    try:
        r = httpx.post(f"{API}/api/encounter", json=enc_start, timeout=5)
        body = r.json()
        check("enc start-contact status", r.status_code == 200, str(r.status_code))
        check("enc start-contact t", body.get("t_fraction") == "0/1", str(body))
        check("enc start-contact seg a", body.get("fly_a", {}).get("segment_index") == 0, str(body))
        check("enc start-contact seg b", body.get("fly_b", {}).get("segment_index") == 0, str(body))
        check("enc start-contact point",
              body.get("contact_display") == {"x": "1000", "y": "500"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc start-contact request", False, repr(e))

    # 8b) 分段数不同（A 两段、B 三段）中途首次相撞：t=8/19，A 在第 0 段、B 在第 1 段
    enc_mid = {
        "stage": {"width": 10000, "height": 10000},
        "fly_a": {"id": "A", "width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 3000},
                  "waypoints": [{"x": 5000, "y": 3000}],
                  "end": {"x": 9000, "y": 3000}},
        "fly_b": {"id": "B", "width": 1000, "height": 1000,
                  "start": {"x": 9000, "y": 2000},
                  "waypoints": [{"x": 6000, "y": 4000}, {"x": 3000, "y": 4000}],
                  "end": {"x": 0, "y": 2000}},
    }
    try:
        r = httpx.post(f"{API}/api/encounter", json=enc_mid, timeout=5)
        body = r.json()
        check("enc mid status 200", r.status_code == 200, str(r.status_code))
        check("enc mid t exact", body.get("t_fraction") == "8/19", str(body))
        check("enc mid t display", body.get("t_display") == "0.421053", str(body))
        check("enc mid seg a", body.get("fly_a", {}).get("segment_index") == 0, str(body))
        check("enc mid seg b", body.get("fly_b", {}).get("segment_index") == 1, str(body))
        check("enc mid a pos", body.get("fly_a", {}).get("position_display") ==
              {"x": "4210.526316", "y": "3000"}, str(body))
        check("enc mid b pos", body.get("fly_b", {}).get("position_display") ==
              {"x": "5210.526316", "y": "4000"}, str(body))
        check("enc mid contact", body.get("contact_display") ==
              {"x": "5210.526316", "y": "4000"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc mid request", False, repr(e))

    # 8c) 时间错开全程安全：B 先穿过走廊，A 后抵达
    enc_safe = {
        "stage": {"width": 10000, "height": 10000},
        "fly_a": {"id": "A", "width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 4500},
                  "waypoints": [{"x": 4500, "y": 4500}],
                  "end": {"x": 9000, "y": 4500}},
        "fly_b": {"id": "B", "width": 1000, "height": 1000,
                  "start": {"x": 8000, "y": 0}, "end": {"x": 8000, "y": 9000}},
    }
    try:
        r = httpx.post(f"{API}/api/encounter", json=enc_safe, timeout=5)
        body = r.json()
        check("enc safe status", r.status_code == 200 and body.get("collides") is False, r.text[:200])
        check("enc safe null poses", body.get("fly_a") is None and body.get("contact") is None, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc safe request", False, repr(e))

    # 8d) 第二套吊景字段越界 → 400 + fly_b.start.x（沿用统一错误信封）
    enc_bad_b = {
        "stage": {"width": 10000, "height": 10000},
        "fly_a": {"id": "A", "width": 1000, "height": 1000,
                  "start": {"x": 0, "y": 0}, "end": {"x": 1000, "y": 0}},
        "fly_b": {"id": "B", "width": 1000, "height": 1000,
                  "start": {"x": 9001, "y": 0}, "end": {"x": 0, "y": 0}},
    }
    try:
        r = httpx.post(f"{API}/api/encounter", json=enc_bad_b, timeout=5)
        err = r.json().get("error", {})
        check("enc fly_b oob 400", r.status_code == 400, str(r.status_code))
        check("enc fly_b oob path", err.get("path") == "fly_b.start.x", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("enc fly_b oob request", False, repr(e))

    # 8e) 两套吊景编号相同 → 400 + fly_b.id
    enc_same_id = {
        "stage": {"width": 10000, "height": 10000},
        "fly_a": {**enc_safe["fly_a"]},
        "fly_b": {**enc_safe["fly_b"], "id": "A"},
    }
    try:
        r = httpx.post(f"{API}/api/encounter", json=enc_same_id, timeout=5)
        err = r.json().get("error", {})
        check("enc same id 400", r.status_code == 400, str(r.status_code))
        check("enc same id path", err.get("path") == "fly_b.id", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("enc same id request", False, repr(e))

    # 8f) 原有单吊景检查接口继续可用（命中既有 collision 结果，字段不回归）
    try:
        r = httpx.post(f"{API}/api/check", json=collision, timeout=5)
        body = r.json()
        check("legacy check still works",
              r.status_code == 200 and body.get("t_display") == "0.333333"
              and body.get("segment_index") == 0, str(body))
    except Exception as e:  # noqa: BLE001
        check("legacy check request", False, repr(e))

    # 8g) duration_weights：走廊方案等时基线 t=4/9 在 A 第 0 段相撞（未加权不回归）
    corr_a = {"id": "A", "width": 1000, "height": 1000,
              "start": {"x": 0, "y": 4500},
              "waypoints": [{"x": 4500, "y": 4500}],
              "end": {"x": 9000, "y": 4500}}
    corr_b = {"id": "B", "width": 1000, "height": 1000,
              "start": {"x": 5000, "y": 0}, "end": {"x": 5000, "y": 9000}}
    try:
        r = httpx.post(f"{API}/api/encounter",
                       json={"stage": {"width": 10000, "height": 10000},
                             "fly_a": corr_a, "fly_b": corr_b}, timeout=5)
        body = r.json()
        check("enc corridor equal-time status", r.status_code == 200, str(r.status_code))
        check("enc corridor equal-time t", body.get("t_fraction") == "4/9", str(body))
        check("enc corridor equal-time seg a", body.get("fly_a", {}).get("segment_index") == 0, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc corridor equal-time request", False, repr(e))

    # 8h) A 加权 [3,1]：首段耗时 3/4，抵达走廊时 B 已穿过 → 原本相撞变为全程安全
    try:
        r = httpx.post(f"{API}/api/encounter",
                       json={"stage": {"width": 10000, "height": 10000},
                             "fly_a": {**corr_a, "duration_weights": [3, 1]},
                             "fly_b": corr_b}, timeout=5)
        body = r.json()
        check("enc weighted stagger status", r.status_code == 200, str(r.status_code))
        check("enc weighted stagger safe", body.get("collides") is False, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc weighted stagger request", False, repr(e))

    # 8i) A 加权 [1,3]：首次接触改在 A 第 1 段，t=7/18
    try:
        r = httpx.post(f"{API}/api/encounter",
                       json={"stage": {"width": 10000, "height": 10000},
                             "fly_a": {**corr_a, "duration_weights": [1, 3]},
                             "fly_b": corr_b}, timeout=5)
        body = r.json()
        check("enc weighted hit status", r.status_code == 200, str(r.status_code))
        check("enc weighted hit t", body.get("t_fraction") == "7/18", str(body))
        check("enc weighted hit seg a", body.get("fly_a", {}).get("segment_index") == 1, str(body))
        check("enc weighted hit seg b", body.get("fly_b", {}).get("segment_index") == 0, str(body))
        check("enc weighted hit contact",
              body.get("contact_display") == {"x": "5666.666667", "y": "4500"}, str(body))
    except Exception as e:  # noqa: BLE001
        check("enc weighted hit request", False, repr(e))

    # 8j) 权重长度与段数不符 → 400 + fly_a.duration_weights
    try:
        r = httpx.post(f"{API}/api/encounter",
                       json={"stage": {"width": 10000, "height": 10000},
                             "fly_a": {**corr_a, "duration_weights": [1, 2, 3]},
                             "fly_b": corr_b}, timeout=5)
        err = r.json().get("error", {})
        check("enc weights length 400", r.status_code == 400, str(r.status_code))
        check("enc weights length path", err.get("path") == "fly_a.duration_weights", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("enc weights length request", False, repr(e))

    # 8k) 非正权重 → 400 + 具体下标 fly_a.duration_weights.1
    try:
        r = httpx.post(f"{API}/api/encounter",
                       json={"stage": {"width": 10000, "height": 10000},
                             "fly_a": {**corr_a, "duration_weights": [1, 0]},
                             "fly_b": corr_b}, timeout=5)
        err = r.json().get("error", {})
        check("enc weights zero 400", r.status_code == 400, str(r.status_code))
        check("enc weights zero path", err.get("path") == "fly_a.duration_weights.1", r.text[:200])
    except Exception as e:  # noqa: BLE001
        check("enc weights zero request", False, repr(e))

    # 8l) 超大权重仍按精确有理数处理，不因位数被拦截或溢出：
    #     [2^53+1, 1]（16 位，末位超出双精度安全整数）首段极慢 → 全程安全
    #     [10^309, 1]（310 位，超过 double MAX_VALUE）同样全程安全
    #     [5×10^308, 5×10^308]（两个 309 位等权）等价等时基线 → t=4/9 仍在 A 第 0 段相撞
    huge_cases = [
        ("enc 16-digit weight safe", [2**53 + 1, 1], False, None),
        ("enc 310-digit weight safe", [10**309, 1], False, None),
        ("enc twin 309-digit weights hit", [5 * 10**308, 5 * 10**308], True, "4/9"),
    ]
    for name, weights, collides, t_fraction in huge_cases:
        try:
            r = httpx.post(f"{API}/api/encounter",
                           json={"stage": {"width": 10000, "height": 10000},
                                 "fly_a": {**corr_a, "duration_weights": weights},
                                 "fly_b": corr_b}, timeout=10)
            body = r.json()
            ok = r.status_code == 200 and body.get("collides") is collides
            if t_fraction is not None:
                ok = ok and body.get("t_fraction") == t_fraction
            check(name, ok, str(body)[:300])
        except Exception as e:  # noqa: BLE001
            check(f"{name} request", False, repr(e))

    # 9) Web 页面内容
    try:
        r = httpx.get(f"{WEB}/", timeout=5)
        check("web html", r.status_code == 200 and '<div id="root">' in r.text, r.text[:120])
    except Exception as e:  # noqa: BLE001
        check("web request", False, repr(e))

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}", flush=True)
        return 1
    print("\nAll checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
