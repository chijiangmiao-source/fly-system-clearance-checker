"""API 联调测试：校验错误的首个字段路径、碰撞结果与 half-up 展示值。"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

STAGE = {"width": 10000, "height": 10000}
FLY = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500}}
ZONE = {"id": "A", "vertices": [{"x": 4000, "y": 0}, {"x": 6000, "y": 0}, {"x": 6000, "y": 2000}, {"x": 4000, "y": 2000}]}


def payload(**over):
    base = {"stage": dict(STAGE), "fly": json.loads(json.dumps(FLY)), "zones": [json.loads(json.dumps(ZONE))]}
    base.update(over)
    return base


def post(body) -> tuple[int, dict]:
    if isinstance(body, str):
        r = client.post("/api/check", content=body, headers={"Content-Type": "application/json; charset=utf-8"})
    else:
        r = client.post("/api/check", content=json.dumps(body), headers={"Content-Type": "application/json; charset=utf-8"})
    return r.status_code, r.json()


class TestCollisionResults:
    def test_head_on_collision(self):
        code, body = post(payload())
        assert code == 200
        assert body["collides"] is True
        assert body["t_display"] == "0.333333"
        assert body["t_fraction"] == "1/3"
        assert body["zone_id"] == "A"
        assert body["zone_index"] == 0
        assert body["edge_index"] == 3
        assert body["position"] == {"x": pytest.approx(3000.0), "y": pytest.approx(500.0)}
        assert body["position_display"] == {"x": "3000", "y": "500"}

    def test_half_up_rounding_two_thirds(self):
        # t = 2/3 = 0.666666… → 0.666667
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500}}
        z = {"id": "A", "vertices": [{"x": 7000, "y": 0}, {"x": 9000, "y": 0}, {"x": 9000, "y": 2000}, {"x": 7000, "y": 2000}]}
        code, body = post(payload(fly=fly, zones=[z]))
        assert code == 200
        assert body["t_display"] == "0.666667"
        assert body["t_fraction"] == "2/3"

    def test_half_up_rounding_one_sixth(self):
        # t = 1/6 = 0.166666… → 0.166667；右缘 x=6000t+1000=2000 → t=1/6
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 6000, "y": 500}}
        z = {"id": "A", "vertices": [{"x": 2000, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 2000}, {"x": 2000, "y": 2000}]}
        code, body = post(payload(fly=fly, zones=[z]))
        assert code == 200
        assert body["t_display"] == "0.166667"

    def test_no_collision_all_clear(self):
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 3000}, "end": {"x": 9000, "y": 3000}}
        code, body = post(payload(fly=fly))
        assert code == 200
        assert body["collides"] is False
        assert body["t"] is None
        assert body["t_display"] is None
        assert body["zone_id"] is None
        assert body["edge_index"] is None

    def test_empty_zones_never_collides(self):
        code, body = post(payload(zones=[]))
        assert code == 200
        assert body["collides"] is False

    def test_inside_zone_at_start(self):
        fly = {"width": 1000, "height": 1000, "start": {"x": 1000, "y": 1000}, "end": {"x": 5000, "y": 5000}}
        z = {"id": "Z", "vertices": [{"x": 0, "y": 0}, {"x": 9000, "y": 0}, {"x": 9000, "y": 9000}, {"x": 0, "y": 9000}]}
        code, body = post(payload(fly=fly, zones=[z]))
        assert code == 200
        assert body["collides"] is True
        assert body["t_display"] == "0.000000"
        assert body["edge_index"] == 0
        assert body["zone_id"] == "Z"

    def test_touch_at_end_t_one(self):
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 3000, "y": 500}}
        code, body = post(payload(fly=fly))
        assert code == 200
        assert body["t_display"] == "1.000000"
        assert body["edge_index"] == 3

    def test_tie_break_lexicographic_zone_id(self):
        za = {"id": "A", "vertices": [{"x": 4000, "y": 1000}, {"x": 5000, "y": 1000}, {"x": 5000, "y": 2000}, {"x": 4000, "y": 2000}]}
        zb = {"id": "B", "vertices": [{"x": 4000, "y": 0}, {"x": 5000, "y": 0}, {"x": 5000, "y": 1000}, {"x": 4000, "y": 1000}]}
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 0}, "end": {"x": 9000, "y": 0}}
        code, body = post(payload(fly=fly, zones=[zb, za]))
        assert code == 200
        assert body["zone_id"] == "A"
        assert body["zone_index"] == 1
        assert body["t_display"] == "0.333333"


class TestValidationErrors:
    def test_invalid_json_body(self):
        code, body = post("{not json")
        assert code == 400
        assert body["error"]["path"] == ""

    def test_root_not_object(self):
        code, body = post("[1, 2, 3]")
        assert code == 400
        assert body["error"]["path"] == ""

    def test_missing_stage(self):
        p = payload()
        del p["stage"]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "stage"

    def test_stage_size_not_fixed(self):
        code, body = post(payload(stage={"width": 9999, "height": 10000}))
        assert code == 400
        assert body["error"]["path"] == "stage.width"

    def test_missing_fly_start_x(self):
        p = payload()
        del p["fly"]["start"]["x"]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_non_integer_width(self):
        p = payload()
        p["fly"]["width"] = 1000.5
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.width"

    def test_integer_valued_float_rejected(self):
        p = payload()
        p["fly"]["width"] = 1000.0
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.width"

    def test_boolean_rejected_as_integer(self):
        p = payload()
        p["fly"]["start"]["x"] = True
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_zero_width_degenerate(self):
        p = payload()
        p["fly"]["width"] = 0
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.width"

    def test_fly_out_of_bounds_negative(self):
        p = payload()
        p["fly"]["start"]["x"] = -1
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_fly_out_of_bounds_top(self):
        p = payload()
        p["fly"]["end"]["y"] = 9001  # 9001 + 1000 > 10000
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.end.y"

    def test_fly_at_exact_boundary_ok(self):
        p = payload()
        p["fly"]["end"] = {"x": 9000, "y": 9000}  # 9000 + 1000 == 10000 边界允许
        code, body = post(p)
        assert code == 200

    def test_zone_vertex_out_of_bounds(self):
        p = payload()
        p["zones"][0]["vertices"][1] = {"x": 10001, "y": 0}
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices.1.x"

    def test_zone_vertex_non_integer(self):
        p = payload()
        p["zones"][0]["vertices"][2]["y"] = "2000"
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices.2.y"

    def test_zone_missing_id(self):
        p = payload()
        del p["zones"][0]["id"]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.id"

    def test_zone_too_few_vertices(self):
        p = payload()
        p["zones"][0]["vertices"] = p["zones"][0]["vertices"][:2]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"

    def test_zone_zero_area_degenerate(self):
        # 共线三点：闭合边沿原路折返，属自交/退化，错误定位到 vertices
        p = payload()
        p["zones"][0]["vertices"] = [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 2}]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"

    def test_zone_duplicate_vertex_degenerate(self):
        p = payload()
        p["zones"][0]["vertices"] = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 0}, {"x": 0, "y": 100}]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"

    def test_zone_self_intersecting_bowtie(self):
        p = payload()
        p["zones"][0]["vertices"] = [{"x": 0, "y": 0}, {"x": 100, "y": 100}, {"x": 100, "y": 0}, {"x": 0, "y": 100}]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"
        assert "self-intersect" in body["error"]["message"]

    def test_zone_vertex_on_nonadjacent_edge(self):
        # 顶点落在非相邻边上：T 形触碰也算自交
        p = payload()
        p["zones"][0]["vertices"] = [
            {"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100},
            {"x": 50, "y": 100}, {"x": 50, "y": 0},
        ]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"

    def test_first_error_in_document_order(self):
        # stage 与 fly 同时出错时，先报 stage 的字段
        p = payload(stage={"width": 1, "height": 1})
        p["fly"]["width"] = -5
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "stage.width"

    def test_zones_must_be_array(self):
        code, body = post(payload(zones={"id": "A"}))
        assert code == 400
        assert body["error"]["path"] == "zones"

    def test_error_body_shape(self):
        p = payload()
        del p["fly"]["start"]["x"]
        code, body = post(p)
        assert code == 400
        assert set(body.keys()) == {"error"}
        assert set(body["error"].keys()) == {"path", "message"}


class TestExtremelyLongIntegers:
    """超长整数（超过 CPython 默认 4300 位转换上限）不得导致 500。"""

    def test_stage_width_long_integer(self):
        big = "9" * 5000
        text = (
            '{"stage":{"width":%s,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "stage.width"

    def test_stage_height_long_integer(self):
        big = "9" * 6000
        text = (
            '{"stage":{"width":10000,"height":%s},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "stage.height"

    def test_fly_coordinate_long_integer(self):
        p = payload()
        p["fly"]["start"]["x"] = int("8" * 5000)
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_fly_width_long_integer(self):
        # 宽度本身为正整数，但无法容纳于台口 → 越界报在首个坐标字段
        p = payload()
        p["fly"]["width"] = int("9" * 5000)
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_zone_vertex_long_integer(self):
        p = payload()
        p["zones"][0]["vertices"][0]["x"] = int("7" * 5000)
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices.0.x"

    def test_beyond_relaxed_limit_still_points_to_field(self):
        # 超过十万位也不再做整体拒绝：parse_int 钩子惰性化后照常定位字段
        big = "1" * 200_000
        text = (
            '{"stage":{"width":%s,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "stage.width"

    def test_million_digit_integer_fast_and_located(self):
        # 百万位整数：解析不做精确转换，应迅速返回且定位到字段
        import time

        big = "7" * 1_000_000
        text = (
            '{"stage":{"width":10000,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[{"id":"A","vertices":[{"x":%s,"y":0},{"x":10,"y":0},{"x":0,"y":10}]}]}' % big
        )
        t0 = time.perf_counter()
        code, body = post(text)
        elapsed = time.perf_counter() - t0
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices.0.x"
        assert elapsed < 5

    def test_negative_long_integer(self):
        big = "-" + "9" * 5000
        text = (
            '{"stage":{"width":10000,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":%s,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"
