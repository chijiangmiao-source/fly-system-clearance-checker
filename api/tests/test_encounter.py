"""双吊景交会分析测试。

覆盖验收四场景：
  1) 起始即接触（边界接触也算冲突，t=0）；
  2) 双方分段数不同时中途首次相撞（精确有理数时刻、双方段号、接触位置）；
  3) 时间错开、空间交会窗口不重叠 → 全程安全；
  4) 第二套吊景字段越界 → 400 + fly_b.* 字段路径。
另含编号相异校验、折点接触归前段、JSON 语法错误信封等。
"""

import json
import random
from bisect import bisect_right
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.encounter import cumulative_breaks, encounter_first_contact, route_points
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


# ---------------------------------------------------------------------------
# duration_weights：各路线段相对耗时（正整数数组，省略时各段等时）
# ---------------------------------------------------------------------------

# 走廊方案：A 两段水平穿过 y∈[4500,5500]，B 竖直穿过 x∈[5000,6000] 走廊。
# 等时基线：t=4/9 在走廊口相撞（A 第 0 段）；改权重可错开或改换命中段。
WGT_A = {"id": "A", "width": 1000, "height": 1000,
         "start": {"x": 0, "y": 4500},
         "waypoints": [{"x": 4500, "y": 4500}],
         "end": {"x": 9000, "y": 4500}}
WGT_B = {"id": "B", "width": 1000, "height": 1000,
         "start": {"x": 5000, "y": 0}, "end": {"x": 5000, "y": 9000}}
# B 带停位的版本（两段竖直），用于双方同时加权
WGT_B2 = {"id": "B", "width": 1000, "height": 1000,
          "start": {"x": 5000, "y": 0},
          "waypoints": [{"x": 5000, "y": 4500}],
          "end": {"x": 5000, "y": 9000}}


def run_encounter(fly_a: dict, fly_b: dict):
    d = validate_encounter(enc(fly_a, fly_b))
    return encounter_first_contact(d["fly_a"], d["fly_b"])


class TestDurationWeightsGeometry:
    def test_equal_time_baseline_collides_on_first_segment(self):
        got = run_encounter(WGT_A, WGT_B)
        assert got is not None
        t, ia, ua, ib, ub, (pa, pb, contact) = got
        assert t == Fraction(4, 9)
        assert ia == 0 and ua == Fraction(8, 9)
        assert ib == 0 and ub == Fraction(4, 9)
        assert pa == (4000, 4500)
        assert pb == (5000, 4000)
        assert contact == (5000, 4750)

    def test_weights_stagger_collision_into_safe(self):
        # A 首段耗时 3/4：抵达走廊时 B 已穿过 → 原本相撞变为全程安全
        got = run_encounter(dict(WGT_A, duration_weights=[3, 1]), WGT_B)
        assert got is None

    def test_weights_move_first_contact_to_later_segment(self):
        # A 首段耗时 1/4：提前穿过走廊口，首次接触改在 A 的第 1 段
        got = run_encounter(dict(WGT_A, duration_weights=[1, 3]), WGT_B)
        assert got is not None
        t, ia, ua, ib, ub, (pa, pb, contact) = got
        assert t == Fraction(7, 18)
        assert ia == 1 and ua == Fraction(5, 27)
        assert ib == 0 and ub == Fraction(7, 18)
        assert pa == (Fraction(16000, 3), 4500)
        assert pb == (5000, 3500)
        assert contact == (Fraction(17000, 3), 4500)

    def test_both_flies_weighted(self):
        # 双方各两段、权重均 [3,1]：t=2/3 在走廊口相撞，双方都在第 0 段
        got = run_encounter(
            dict(WGT_A, duration_weights=[3, 1]),
            dict(WGT_B2, duration_weights=[3, 1]),
        )
        assert got is not None
        t, ia, ua, ib, ub, (pa, pb, contact) = got
        assert t == Fraction(2, 3)
        assert ia == 0 and ua == Fraction(8, 9)
        assert ib == 0 and ub == Fraction(8, 9)
        assert contact == (5000, 4750)

    def test_all_ones_weights_match_omitted(self):
        plain = run_encounter(WGT_A, WGT_B)
        weighted = run_encounter(
            dict(WGT_A, duration_weights=[1, 1]),
            dict(WGT_B, duration_weights=[1]),
        )
        assert weighted == plain

    def test_single_segment_weight_is_noop(self):
        plain = run_encounter(WGT_A, WGT_B)
        got = run_encounter(WGT_A, dict(WGT_B, duration_weights=[5]))
        assert got == plain

    def test_random_weighted_routes_cross_checked_by_exact_sampling(self):
        # 随机路线 + 随机权重：以精确有理数稠密采样（1200 组）交叉核对
        rng = random.Random(20260913)
        for _ in range(1200):
            fly_a = _random_weighted_fly(rng, "A")
            fly_b = _random_weighted_fly(rng, "B")
            d = validate_encounter(enc(fly_a, fly_b))
            fa, fb = d["fly_a"], d["fly_b"]
            got = encounter_first_contact(fa, fb)
            samples = [Fraction(k, 480) for k in range(481)]
            overlaps = {
                s for s in samples if _rects_overlap(_pose_at(fa, s), _pose_at(fb, s))
            }
            if got is None:
                assert not overlaps
                continue
            t = got[0]
            # 首次接触之前（采样精度内）不得有接触；接触时刻本身确实相交
            assert all(s >= t for s in overlaps)
            assert _rects_overlap(_pose_at(fa, t), _pose_at(fb, t))


def _random_weighted_fly(rng: random.Random, fly_id: str) -> dict:
    """随机吊景：1–3 段折线（相邻点不重复、全程在台口内）+ 可选权重。"""
    w = h = 1000
    n_wp = rng.randint(0, 2)
    pts = []
    while len(pts) < n_wp + 2:
        p = {"x": rng.randint(0, 9000), "y": rng.randint(0, 9000)}
        if not pts or p != pts[-1]:
            pts.append(p)
    fly = {
        "id": fly_id,
        "width": w,
        "height": h,
        "start": pts[0],
        "end": pts[-1],
    }
    if n_wp:
        fly["waypoints"] = pts[1:-1]
    if rng.random() < 0.7:
        fly["duration_weights"] = [rng.randint(1, 5) for _ in range(n_wp + 1)]
    return fly


def _pose_at(fly: dict, t: Fraction) -> tuple[Fraction, Fraction, int, int]:
    """时刻 t 的精确矩形（左下 x、y 与宽、高），按 duration_weights 计时。"""
    pts = route_points(fly)
    breaks = cumulative_breaks(len(pts) - 1, fly.get("duration_weights"))
    if t >= 1:
        seg = len(pts) - 2
    else:
        seg = bisect_right(breaks, t) - 1
    u = (t - breaks[seg]) / (breaks[seg + 1] - breaks[seg])
    x = pts[seg][0] + u * (pts[seg + 1][0] - pts[seg][0])
    y = pts[seg][1] + u * (pts[seg + 1][1] - pts[seg][1])
    return x, y, fly["width"], fly["height"]


def _rects_overlap(a: tuple, b: tuple) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax <= bx + bw and bx <= ax + aw and ay <= by + bh and by <= ay + ah


class TestDurationWeightsApi:
    def test_weighted_safe_response(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[3, 1]), WGT_B))
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

    def test_weighted_collision_response_fields(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[1, 3]), WGT_B))
        assert code == 200, body
        assert body["collides"] is True
        assert body["t_fraction"] == "7/18"
        assert body["t_display"] == "0.388889"
        assert body["fly_a"]["segment_index"] == 1
        assert body["fly_a"]["segment_t_display"] == "0.185185"
        assert body["fly_a"]["position_display"] == {"x": "5333.333333", "y": "4500"}
        assert body["fly_b"]["segment_index"] == 0
        assert body["fly_b"]["segment_t_display"] == "0.388889"
        assert body["fly_b"]["position_display"] == {"x": "5000", "y": "3500"}
        assert body["contact_display"] == {"x": "5666.666667", "y": "4500"}

    def test_both_weighted_response_fields(self):
        code, body = post(enc(
            dict(WGT_A, duration_weights=[3, 1]),
            dict(WGT_B2, duration_weights=[3, 1]),
        ))
        assert code == 200, body
        assert body["t_fraction"] == "2/3"
        assert body["t_display"] == "0.666667"
        assert body["fly_a"]["segment_index"] == 0
        assert body["fly_b"]["segment_index"] == 0
        assert body["contact_display"] == {"x": "5000", "y": "4750"}

    def test_unweighted_response_unchanged(self):
        # 未提供权重时仍按各段等时分析，响应与既有行为一致
        code, body = post(enc(WGT_A, WGT_B))
        assert code == 200, body
        assert body["t_fraction"] == "4/9"
        assert body["t_display"] == "0.444444"
        assert body["fly_a"]["segment_index"] == 0
        assert body["fly_a"]["segment_t_display"] == "0.888889"
        assert body["fly_b"]["segment_index"] == 0
        assert body["contact_display"] == {"x": "5000", "y": "4750"}

    def test_all_ones_weights_response_matches_omitted(self):
        _, plain = post(enc(WGT_A, WGT_B))
        _, weighted = post(enc(
            dict(WGT_A, duration_weights=[1, 1]),
            dict(WGT_B, duration_weights=[1]),
        ))
        assert weighted == plain


class TestDurationWeightsValidation:
    def test_length_mismatch_locates_weights_of_first_fly(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[1, 2, 3]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights"

    def test_length_mismatch_locates_weights_of_second_fly(self):
        code, body = post(enc(WGT_A, dict(WGT_B, duration_weights=[1, 2])))
        assert code == 400
        assert body["error"]["path"] == "fly_b.duration_weights"

    def test_empty_weights_rejected_by_length(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights"

    def test_zero_weight_locates_index(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[1, 0]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights.1"
        assert "positive" in body["error"]["message"]

    def test_negative_weight_locates_index(self):
        code, body = post(enc(WGT_A, dict(WGT_B, duration_weights=[-2])))
        assert code == 400
        assert body["error"]["path"] == "fly_b.duration_weights.0"

    def test_non_integer_weight_locates_index(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[1.5, 1]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights.0"
        assert "integer" in body["error"]["message"]

    def test_string_weight_locates_index(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[1, "2"]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights.1"

    def test_bool_weight_is_not_an_integer(self):
        code, body = post(enc(dict(WGT_A, duration_weights=[True, 1]), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights.0"

    def test_weights_must_be_an_array(self):
        code, body = post(enc(dict(WGT_A, duration_weights=3), WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.duration_weights"
        assert "array" in body["error"]["message"]

    def test_single_segment_weights_accepted(self):
        code, body = post(enc(WGT_A, dict(WGT_B, duration_weights=[5])))
        assert code == 200
        assert body["collides"] is True

    def test_route_error_precedes_weights_error(self):
        # 按路线顺序先校验路线本身：停位越界先于 duration_weights 错误
        bad = dict(WGT_A, duration_weights=[0, 0])
        bad["waypoints"] = [{"x": 4500, "y": 9001}]
        code, body = post(enc(bad, WGT_B))
        assert code == 400
        assert body["error"]["path"] == "fly_a.waypoints.0.y"

    def test_validate_normalizes_weights(self):
        d = validate_encounter(enc(
            dict(WGT_A, duration_weights=[2, 3]),
            dict(WGT_B, duration_weights=[4]),
        ))
        assert d["fly_a"]["duration_weights"] == [2, 3]
        assert d["fly_b"]["duration_weights"] == [4]
        d2 = validate_encounter(enc(WGT_A, WGT_B))
        assert d2["fly_a"]["duration_weights"] is None
        assert d2["fly_b"]["duration_weights"] is None

    def test_single_fly_check_ignores_duration_weights(self):
        # 既有单吊景检测不回归：fly.duration_weights 不影响 /api/check
        fly = {"width": 1000, "height": 1000,
               "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500},
               "duration_weights": [0]}
        zones = [{"id": "A", "vertices": [{"x": 4000, "y": 0}, {"x": 6000, "y": 0},
                                          {"x": 6000, "y": 2000}, {"x": 4000, "y": 2000}]}]
        r = client.post("/api/check", content=json.dumps(
            {"stage": dict(STAGE), "fly": fly, "zones": zones}),
            headers={"Content-Type": "application/json; charset=utf-8"})
        assert r.status_code == 200
        assert r.json()["t_display"] == "0.333333"
