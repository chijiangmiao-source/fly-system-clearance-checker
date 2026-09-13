"""双吊景交会分析测试。

覆盖验收四场景：
  1) 起始即接触（边界接触也算冲突，t=0）；
  2) 双方分段数不同时中途首次相撞（精确有理数时刻、双方段号、接触位置）；
  3) 时间错开、空间交会窗口不重叠 → 全程安全；
  4) 第二套吊景字段越界 → 400 + fly_b.* 字段路径。
另含编号相异校验、折点接触归前段、JSON 语法错误信封等。
"""

import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.encounter import encounter_first_contact
from app.main import app
from app.validation import FieldError, validate_encounter

client = TestClient(app)

STAGE = {"width": 10000, "height": 10000}


def enc(fly_a: dict, fly_b: dict) -> dict:
    return {"stage": dict(STAGE), "fly_a": fly_a, "fly_b": fly_b}


def post(body) -> tuple[int, dict]:
    if isinstance(body, str):
        r = client.post("/api/encounter", content=body,
                        headers={"Content-Type": "application/json; charset=utf-8"})
    else:
        r = client.post("/api/encounter", content=json.dumps(body),
                        headers={"Content-Type": "application/json; charset=utf-8"})
    return r.status_code, r.json()


# 场景 1：t=0 即共边接触
START_TOUCH_A = {"id": "A", "width": 1000, "height": 1000,
                 "start": {"x": 0, "y": 0}, "end": {"x": 4000, "y": 0}}
START_TOUCH_B = {"id": "B", "width": 1000, "height": 1000,
                 "start": {"x": 1000, "y": 0}, "end": {"x": 5000, "y": 0}}

# 场景 2：A 两段水平、B 三段折线，分段数不同；t=8/19 角点首次相撞
MID_A = {"id": "A", "width": 1000, "height": 1000,
         "start": {"x": 0, "y": 3000},
         "waypoints": [{"x": 5000, "y": 3000}],
         "end": {"x": 9000, "y": 3000}}
MID_B = {"id": "B", "width": 1000, "height": 1000,
         "start": {"x": 9000, "y": 2000},
         "waypoints": [{"x": 6000, "y": 4000}, {"x": 3000, "y": 4000}],
         "end": {"x": 0, "y": 2000}}

# 场景 3：B 先竖直穿过走廊（t≈0.39–0.61），A 后水平抵达（t≥7/9）→ 时间错开全程安全
TIME_A = {"id": "A", "width": 1000, "height": 1000,
          "start": {"x": 0, "y": 4500},
          "waypoints": [{"x": 4500, "y": 4500}],
          "end": {"x": 9000, "y": 4500}}
TIME_B = {"id": "B", "width": 1000, "height": 1000,
          "start": {"x": 8000, "y": 0}, "end": {"x": 8000, "y": 9000}}


class TestEncounterGeometry:
    def test_scenario1_contact_at_start_counts(self):
        d = validate_encounter(enc(START_TOUCH_A, START_TOUCH_B))
        got = encounter_first_contact(d["fly_a"], d["fly_b"])
        assert got is not None
        t, ia, ua, ib, ub, (pa, pb, contact) = got
        assert t == 0
        assert ia == 0 and ib == 0
        assert ua == 0 and ub == 0
        assert pa == (0, 0)
        assert pb == (1000, 0)
        # 共边 x=1000 的中点
        assert contact == (1000, 500)

    def test_scenario2_different_segment_counts_mid_collision(self):
        d = validate_encounter(enc(MID_A, MID_B))
        got = encounter_first_contact(d["fly_a"], d["fly_b"])
        assert got is not None
        t, ia, ua, ib, ub, (pa, pb, contact) = got
        # A 在第 0 段（16/19），B 在第 1 段（5/19）；全程 t=8/19
        assert t == Fraction(8, 19)
        assert ia == 0 and ua == Fraction(16, 19)
        assert ib == 1 and ub == Fraction(5, 19)
        assert pa == (Fraction(80000, 19), 3000)
        assert pb == (Fraction(99000, 19), 4000)
        # A 右上角与 B 左下角相碰
        assert contact == (Fraction(99000, 19), 4000)

    def test_scenario3_time_staggered_is_safe(self):
        d = validate_encounter(enc(TIME_A, TIME_B))
        assert encounter_first_contact(d["fly_a"], d["fly_b"]) is None

    def test_contact_exactly_at_breakpoint_belongs_to_earlier_segment(self):
        # B 静止于 [5000,6000]×[0,1000]；A 两段，恰在折点 t=1/2（左下角 x=4000）
        # 以右缘 x=5000 触及 B 左缘。折点两侧同时命中 → A 归第 0 段（段内 t=1）
        a = {"id": "A", "width": 1000, "height": 1000,
             "start": {"x": 0, "y": 0},
             "waypoints": [{"x": 4000, "y": 0}],
             "end": {"x": 8000, "y": 0}}
        b = {"id": "B", "width": 1000, "height": 1000,
             "start": {"x": 5000, "y": 0}, "end": {"x": 5000, "y": 0}}
        d = validate_encounter(enc(a, b))
        got = encounter_first_contact(d["fly_a"], d["fly_b"])
        assert got is not None
        t, ia, ua, ib, ub, _ = got
        assert t == Fraction(1, 2)
        assert ia == 0 and ua == 1
        assert ib == 0 and ub == Fraction(1, 2)

    def test_touch_at_final_instant_counts(self):
        # 直到 t=1 两矩形才在台口右侧共边
        a = {"id": "A", "width": 1000, "height": 1000,
             "start": {"x": 0, "y": 0}, "end": {"x": 8000, "y": 0}}
        b = {"id": "B", "width": 1000, "height": 1000,
             "start": {"x": 9000, "y": 0}, "end": {"x": 9000, "y": 0}}
        d = validate_encounter(enc(a, b))
        got = encounter_first_contact(d["fly_a"], d["fly_b"])
        assert got is not None
        assert got[0] == 1


class TestEncounterApi:
    def test_scenario1_start_contact_response(self):
        code, body = post(enc(START_TOUCH_A, START_TOUCH_B))
        assert code == 200
        assert body["collides"] is True
        assert body["t"] == 0.0
        assert body["t_display"] == "0.000000"
        assert body["t_fraction"] == "0/1"
        assert body["fly_a"]["id"] == "A"
        assert body["fly_a"]["segment_index"] == 0
        assert body["fly_a"]["segment_t_display"] == "0.000000"
        assert body["fly_a"]["position_display"] == {"x": "0", "y": "0"}
        assert body["fly_b"]["segment_index"] == 0
        assert body["fly_b"]["position_display"] == {"x": "1000", "y": "0"}
        assert body["contact_display"] == {"x": "1000", "y": "500"}

    def test_scenario2_mid_collision_response_fields(self):
        code, body = post(enc(MID_A, MID_B))
        assert code == 200, body
        assert body["collides"] is True
        assert body["t_fraction"] == "8/19"
        assert body["t_display"] == "0.421053"
        assert body["fly_a"]["id"] == "A"
        assert body["fly_a"]["segment_index"] == 0
        assert body["fly_a"]["segment_t_display"] == "0.842105"
        assert body["fly_a"]["position_display"] == {"x": "4210.526316", "y": "3000"}
        assert body["fly_b"]["id"] == "B"
        assert body["fly_b"]["segment_index"] == 1
        assert body["fly_b"]["segment_t_display"] == "0.263158"
        assert body["fly_b"]["position_display"] == {"x": "5210.526316", "y": "4000"}
        assert body["contact_display"] == {"x": "5210.526316", "y": "4000"}

    def test_scenario3_safe_response(self):
        code, body = post(enc(TIME_A, TIME_B))
        assert code == 200
        assert body == {
            "collides": False,
            "t": None,
            "t_display": None,
            "t_fraction": None,
            "fly_a": None,
            "fly_b": None,
            "contact": None,
            "contact_display": None,
        }

    def test_invalid_json_uses_empty_path_envelope(self):
        code, body = post("{not json")
        assert code == 400
        assert body["error"]["path"] == ""
        assert "JSON" in body["error"]["message"]

    def test_health_still_ok(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestEncounterValidation:
    def test_scenario4_second_fly_start_out_of_bounds(self):
        bad_b = {"id": "B", "width": 1000, "height": 1000,
                 "start": {"x": 9001, "y": 0}, "end": {"x": 0, "y": 0}}
        code, body = post(enc(TIME_A, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_b.start.x"

    def test_second_fly_waypoint_out_of_bounds(self):
        bad_b = dict(MID_B)
        bad_b["waypoints"] = [{"x": 6000, "y": 4000}, {"x": 3000, "y": 9001}]
        code, body = post(enc(MID_A, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_b.waypoints.1.y"

    def test_second_fly_bad_width(self):
        bad_b = {"id": "B", "width": 0, "height": 1000,
                 "start": {"x": 0, "y": 0}, "end": {"x": 1000, "y": 0}}
        code, body = post(enc(TIME_A, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_b.width"

    def test_first_fly_error_reported_before_second(self):
        bad_a = {"id": "A", "width": 1000, "height": 1000,
                 "start": {"x": -1, "y": 0}, "end": {"x": 1000, "y": 0}}
        bad_b = {"id": "B", "width": 0, "height": 1000,
                 "start": {"x": 0, "y": 0}, "end": {"x": 1000, "y": 0}}
        code, body = post(enc(bad_a, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_a.start.x"

    def test_missing_fly_a(self):
        code, body = post({"stage": dict(STAGE), "fly_b": TIME_B})
        assert code == 400
        assert body["error"]["path"] == "fly_a"

    def test_missing_fly_b_id(self):
        code, body = post(enc(TIME_A, {k: v for k, v in TIME_B.items() if k != "id"}))
        assert code == 400
        assert body["error"]["path"] == "fly_b.id"

    def test_id_must_be_string(self):
        bad_b = dict(TIME_B, id=123)
        code, body = post(enc(TIME_A, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_b.id"

    def test_id_must_not_be_empty(self):
        code, body = post(enc(dict(TIME_A, id=""), dict(TIME_B, id="")))
        assert code == 400
        assert body["error"]["path"] == "fly_a.id"

    def test_duplicate_ids_rejected_on_second(self):
        code, body = post(enc(dict(TIME_A, id="SAME"), dict(TIME_B, id="SAME")))
        assert code == 400
        assert body["error"]["path"] == "fly_b.id"
        assert "distinct" in body["error"]["message"]

    def test_duplicate_adjacent_waypoint_in_second_fly(self):
        bad_b = {"id": "B", "width": 1000, "height": 1000,
                 "start": {"x": 0, "y": 0},
                 "waypoints": [{"x": 1000, "y": 0}, {"x": 1000, "y": 0}],
                 "end": {"x": 4000, "y": 0}}
        code, body = post(enc(TIME_A, bad_b))
        assert code == 400
        assert body["error"]["path"] == "fly_b.waypoints.1"

    def test_stage_validated_first(self):
        p = enc(TIME_A, TIME_B)
        p["stage"] = {"width": 1, "height": 10000}
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "stage.width"

    def test_validate_returns_distinct_normalized_flies(self):
        d = validate_encounter(enc(START_TOUCH_A, START_TOUCH_B))
        assert d["fly_a"]["id"] == "A"
        assert d["fly_b"]["id"] == "B"
        assert d["fly_a"]["waypoints"] is None
