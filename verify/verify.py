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

    # 5) Web 页面内容
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
