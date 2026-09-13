"""折线路线（fly.waypoints 中途停位）测试。

- 校验：停位为台口内整数坐标、拒绝相邻重复点（含与起/终点重合）；
- 几何：各段等时复用单段扫掠，段序 + 段内最小 t 汇总，折点两侧命中归前段；
- API：保留原碰撞字段，补充 segment_index 与 segment_t_display；
  不含 waypoints 的单段请求数值与字段含义完全兼容。
"""

import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.geometry import first_collision, first_collision_segmented
from app.main import app
from app.validation import FieldError, validate

client = TestClient(app)

STAGE = {"width": 10000, "height": 10000}
# 水平路线 y=3000，停位 (5000,3000)；禁入区 x∈[7000,9000] y∈[2500,3500]
SEG2_FLY = {
    "width": 1000, "height": 1000,
    "start": {"x": 0, "y": 3000},
    "waypoints": [{"x": 5000, "y": 3000}],
    "end": {"x": 9000, "y": 3000},
}
SEG2_ZONE = {
    "id": "A",
    "vertices": [
        {"x": 7000, "y": 2500}, {"x": 9000, "y": 2500},
        {"x": 9000, "y": 3500}, {"x": 7000, "y": 3500},
    ],
}
# 折点两侧同时命中：矩形左上角在 t=1/2 时抵达区左下顶点 (4000,5000)，
# 下一段从该点沿反 x 方向继续上行 —— 折点两侧都命中，应归前段
VERTEX_FLY = {
    "width": 1000, "height": 1000,
    "start": {"x": 0, "y": 0},
    "waypoints": [{"x": 4000, "y": 4000}],
    "end": {"x": 0, "y": 8000},
}
VERTEX_ZONE = {
    "id": "B",
    "vertices": [
        {"x": 3000, "y": 5000}, {"x": 4000, "y": 5000},
        {"x": 4000, "y": 6000}, {"x": 3000, "y": 6000},
    ],
}


def post(body) -> tuple[int, dict]:
    if isinstance(body, str):
        r = client.post("/api/check", content=body, headers={"Content-Type": "application/json; charset=utf-8"})
    else:
        r = client.post("/api/check", content=json.dumps(body), headers={"Content-Type": "application/json; charset=utf-8"})
    return r.status_code, r.json()


def payload_with(fly: dict, zones: list[dict] | None = None) -> dict:
    return {"stage": dict(STAGE), "fly": fly, "zones": zones if zones is not None else []}


class TestSegmentedGeometry:
    def test_first_hit_in_second_segment(self):
        got = first_collision_segmented(SEG2_FLY, [
            {"id": "A", "vertices": [(7000, 2500), (9000, 2500), (9000, 3500), (7000, 3500)]}
        ])
        assert got is not None
        global_t, seg_index, local_t, zid, edge, zi = got
        # 第二段：右缘 6000+4000t 触 x=7000 → 段内 t=1/4；全程 (1+1/4)/2 = 5/8
        # 接触段与区左缘重合至左上顶点 (7000,3500)：边 2、3 同时刻，取较小边 2
        assert seg_index == 1
        assert local_t == Fraction(1, 4)
        assert global_t == Fraction(5, 8)
        assert zid == "A"
        assert edge == 2
        assert zi == 0

    def test_first_hit_in_third_segment_three_waypoints(self):
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 3000},
            "waypoints": [{"x": 3000, "y": 3000}, {"x": 6000, "y": 3000}],
            "end": {"x": 9000, "y": 3000},
        }
        # 区左缘 x=7500：折点 (6000,*) 处右缘仅到 7000，只有第三段能撞
        got = first_collision_segmented(fly, [
            {"id": "A", "vertices": [(7500, 2500), (9000, 2500), (9000, 3500), (7500, 3500)]}
        ])
        assert got is not None
        global_t, seg_index, local_t, *_ = got
        assert seg_index == 2
        assert local_t == Fraction(1, 6)  # 右缘 7000+3000t=7500
        assert global_t == Fraction(13, 18)

    def test_vertex_hit_belongs_to_earlier_segment(self):
        got = first_collision_segmented(VERTEX_FLY, [
            {"id": "B", "vertices": [(3000, 5000), (4000, 5000), (4000, 6000), (3000, 6000)]}
        ])
        assert got is not None
        global_t, seg_index, local_t, zid, edge, _ = got
        assert global_t == Fraction(1, 2)
        assert seg_index == 0  # 前段 t=1 与后段 t=0 等价时归前段
        assert local_t == Fraction(1)
        assert zid == "B"
        assert edge == 0

    def test_multi_segment_safe_route(self):
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 8000},
            "waypoints": [{"x": 5000, "y": 3000}],
            "end": {"x": 9000, "y": 8000},
        }
        got = first_collision_segmented(fly, [
            {"id": "A", "vertices": [(7000, 2500), (9000, 2500), (9000, 3500), (7000, 3500)]}
        ])
        assert got is None

    def test_no_waypoints_matches_single_segment(self):
        fly_single = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500},
        }
        zones = [{"id": "A", "vertices": [(4000, 0), (6000, 0), (6000, 2000), (4000, 2000)]}]
        single = first_collision(fly_single, zones)
        seg = first_collision_segmented({**fly_single, "waypoints": None}, zones)
        assert single is not None and seg is not None
        assert seg[2] == single[0]       # 段内 t 即原 t
        assert seg[0] == single[0]       # 单段时全程 t 相同
        assert seg[1] == 0
        assert seg[3:] == single[1:]

    def test_empty_waypoints_matches_single_segment(self):
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500},
            "waypoints": [],
        }
        zones = [{"id": "A", "vertices": [(4000, 0), (6000, 0), (6000, 2000), (4000, 2000)]}]
        got = first_collision_segmented(fly, zones)
        assert got is not None
        assert got[0] == Fraction(1, 3)
        assert got[1] == 0
        assert got[2] == Fraction(1, 3)


class TestWaypointApi:
    def test_second_segment_first_hit_fields(self):
        code, body = post(payload_with(SEG2_FLY, [SEG2_ZONE]))
        assert code == 200
        assert body["collides"] is True
        assert body["t_fraction"] == "5/8"
        assert body["t_display"] == "0.625000"
        assert body["segment_index"] == 1
        assert body["segment_t_display"] == "0.250000"
        assert body["zone_id"] == "A"
        # 接触至区左上顶点：边 2、3 同刻，取较小边序号 2
        assert body["edge_index"] == 2
        # 碰撞位置按命中段几何给出：(5000,3000) + 1/4·(4000,0) = (6000,3000)
        assert body["position"] == {"x": pytest.approx(6000.0), "y": pytest.approx(3000.0)}
        assert body["position_display"] == {"x": "6000", "y": "3000"}

    def test_vertex_hit_segment_index_zero(self):
        code, body = post(payload_with(VERTEX_FLY, [VERTEX_ZONE]))
        assert code == 200
        assert body["t_display"] == "0.500000"
        assert body["segment_index"] == 0
        assert body["segment_t_display"] == "1.000000"
        assert body["zone_id"] == "B"
        assert body["edge_index"] == 0
        assert body["position_display"] == {"x": "4000", "y": "4000"}

    def test_multi_segment_all_green(self):
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 8000},
            "waypoints": [{"x": 5000, "y": 3000}],
            "end": {"x": 9000, "y": 8000},
        }
        code, body = post(payload_with(fly, [SEG2_ZONE]))
        assert code == 200
        assert body["collides"] is False
        assert body["segment_index"] is None
        assert body["segment_t_display"] is None
        assert body["t"] is None

    def test_single_segment_response_compatible(self):
        # 不含 waypoints：原字段数值不变，新增 segment_index=0、segment_t_display=t_display
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500},
        }
        code, body = post(payload_with(fly, [
            {"id": "A", "vertices": [
                {"x": 4000, "y": 0}, {"x": 6000, "y": 0},
                {"x": 6000, "y": 2000}, {"x": 4000, "y": 2000},
            ]},
        ]))
        assert code == 200
        assert body["t_display"] == "0.333333"
        assert body["t_fraction"] == "1/3"
        assert body["zone_id"] == "A"
        assert body["zone_index"] == 0
        assert body["edge_index"] == 3
        assert body["position_display"] == {"x": "3000", "y": "500"}
        assert body["segment_index"] == 0
        assert body["segment_t_display"] == "0.333333"

    def test_empty_waypoints_accepted(self):
        fly = dict(SEG2_FLY, waypoints=[])
        # 退化为单段直线 (0,3000)->(9000,3000)：右缘 1000+9000t=7000 → t=2/3
        code, body = post(payload_with(fly, [SEG2_ZONE]))
        assert code == 200
        assert body["segment_index"] == 0
        assert body["segment_t_display"] == body["t_display"]
        assert body["t_fraction"] == "2/3"


class TestWaypointValidation:
    def _base(self, waypoints):
        return payload_with({
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 0},
            "end": {"x": 9000, "y": 9000},
            "waypoints": waypoints,
        })

    def test_waypoint_out_of_bounds_x(self):
        code, body = post(self._base([{"x": 9001, "y": 0}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"

    def test_waypoint_out_of_bounds_y_second_index(self):
        code, body = post(self._base([{"x": 5000, "y": 5000}, {"x": 1, "y": 9001}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.1.y"

    def test_waypoint_non_integer(self):
        code, body = post(self._base([{"x": 500.5, "y": 0}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"

    def test_waypoint_boolean_rejected(self):
        code, body = post(self._base([{"x": False, "y": 0}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"

    def test_waypoint_missing_coord(self):
        code, body = post(self._base([{"y": 0}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"

    def test_waypoint_must_be_object(self):
        code, body = post(self._base([[1, 2]]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0"

    def test_waypoints_must_be_array(self):
        code, body = post(self._base({"x": 1, "y": 2}))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints"

    def test_duplicate_with_start(self):
        code, body = post(self._base([{"x": 0, "y": 0}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0"
        assert "(0, 0)" in body["error"]["message"]

    def test_adjacent_duplicate_points_to_later_index_and_coords(self):
        code, body = post(self._base([{"x": 5000, "y": 5000}, {"x": 5000, "y": 5000}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.1"
        assert "(5000, 5000)" in body["error"]["message"]

    def test_duplicate_with_end(self):
        code, body = post(self._base([{"x": 5000, "y": 5000}, {"x": 9000, "y": 9000}]))
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.1"
        assert "(9000, 9000)" in body["error"]["message"]

    def test_non_adjacent_same_waypoint_allowed(self):
        # 原路折返：非相邻点重复不违反“相邻重复”限制（整段运动仍合法）
        p = self._base([{"x": 5000, "y": 5000}, {"x": 3000, "y": 3000}, {"x": 5000, "y": 5000}])
        code, _ = post(p)
        assert code == 200

    def test_first_error_document_order_waypoints_before_zones(self):
        p = self._base([{"x": -1, "y": 0}])
        p["zones"] = [{"id": "BAD", "vertices": [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}]}]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"

    def test_valid_waypoint_at_stage_boundary(self):
        # 停位使吊景恰好贴齐台口边缘：允许（x=9000 → 右缘 10000）
        code, _ = post(self._base([{"x": 9000, "y": 0}, {"x": 5000, "y": 5000}]))
        assert code == 200

    def test_waypoint_long_integer_located(self):
        big = "9" * 5000
        text = (
            '{"stage":{"width":10000,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},'
            '"waypoints":[{"x":%s,"y":0}],"end":{"x":1000,"y":0}},'
            '"zones":[]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "fly.waypoints.0.x"


class TestWaypointValidationDirect:
    def test_validate_returns_waypoints(self):
        data = validate({
            "stage": {"width": 10000, "height": 10000},
            "fly": {"width": 1000, "height": 1000,
                    "start": {"x": 0, "y": 0}, "end": {"x": 1000, "y": 1000},
                    "waypoints": [{"x": 500, "y": 500}]},
            "zones": [],
        })
        assert data["fly"]["waypoints"] == [{"x": 500, "y": 500}]

    def test_validate_without_waypoints_key(self):
        data = validate({
            "stage": {"width": 10000, "height": 10000},
            "fly": {"width": 1000, "height": 1000,
                    "start": {"x": 0, "y": 0}, "end": {"x": 1000, "y": 1000}},
            "zones": [],
        })
        assert data["fly"]["waypoints"] is None
