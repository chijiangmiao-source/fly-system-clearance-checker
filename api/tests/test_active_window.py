"""禁入区启用窗口（zones[].active_window）测试。

- 校验：选填对象 {start_tick, end_tick}，按禁入区顺序检查
  0 ≤ start_tick ≤ end_tick ≤ 1000000，错误定位到 zones.<i>.active_window 下具体字段；
- 几何：各段接触区间与启用窗口（全程百万分之一刻度）换算到同一精确时间轴，
  仅闭区间重叠（含端点相触）时计碰撞，最早碰撞时刻 = max(首触时刻, 窗口起点)；
- 兼容：未填窗口的旧请求结果不变，折点归属与责任对象决胜行为不变。
"""

import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.geometry import (
    first_collision,
    first_collision_segmented,
    point_segment_contact_interval,
    zone_contact_window,
)
from app.main import app
from app.validation import validate

client = TestClient(app)

STAGE = {"width": 10000, "height": 10000}
# 水平路线 y=500：右缘 t=1/2 触区左缘 x=5500，左缘 t=13/18 离区右缘 x=6500
# → 接触区间 [1/2, 13/18]
FLY = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 500}, "end": {"x": 9000, "y": 500}}
ZONE = {
    "id": "A",
    "vertices": [
        {"x": 5500, "y": 0}, {"x": 6500, "y": 0},
        {"x": 6500, "y": 2000}, {"x": 5500, "y": 2000},
    ],
}
ZONE_VERTS = [(5500, 0), (6500, 0), (6500, 2000), (5500, 2000)]


def windowed_zone(start_tick, end_tick, zid="A", verts=None):
    return {
        "id": zid,
        "vertices": verts if verts is not None else json.loads(json.dumps(ZONE["vertices"])),
        "active_window": {"start_tick": start_tick, "end_tick": end_tick},
    }


def post(body) -> tuple[int, dict]:
    if isinstance(body, str):
        r = client.post("/api/check", content=body, headers={"Content-Type": "application/json; charset=utf-8"})
    else:
        r = client.post("/api/check", content=json.dumps(body), headers={"Content-Type": "application/json; charset=utf-8"})
    return r.status_code, r.json()


def payload_with(zones, fly=None) -> dict:
    return {"stage": dict(STAGE), "fly": json.loads(json.dumps(fly or FLY)), "zones": zones}


class TestPointSegmentContactInterval:
    def test_crossing_point_interval(self):
        # 点 (0,1) 以速度 (4,0) 运动，线段 x=2, y∈[0,2] → 瞬时接触 [1/2, 1/2]
        assert point_segment_contact_interval((0, 1), (4, 0), (2, 0), (2, 2)) == (
            Fraction(1, 2), Fraction(1, 2))

    def test_collinear_interval(self):
        # 点沿线段所在直线滑动，t∈[1/4,1/2] 位于线段上
        assert point_segment_contact_interval((0, 0), (8, 0), (2, 0), (4, 0)) == (
            Fraction(1, 4), Fraction(1, 2))

    def test_collinear_interval_clamped_to_unit(self):
        # 进入时刻早于 0、离开时刻晚于 1：截断到 [0,1]
        assert point_segment_contact_interval((3, 0), (1, 0), (2, 0), (4, 0)) == (
            Fraction(0), Fraction(1))

    def test_collinear_interval_exit_before_one(self):
        # 点 (3,0) 以速度 (8,0) 滑过线段 [2,4]：t=1/8 时离开
        assert point_segment_contact_interval((3, 0), (8, 0), (2, 0), (4, 0)) == (
            Fraction(0), Fraction(1, 8))

    def test_static_on_segment_full_interval(self):
        assert point_segment_contact_interval((3, 0), (0, 0), (2, 0), (4, 0)) == (
            Fraction(0), Fraction(1))

    def test_no_contact(self):
        assert point_segment_contact_interval((0, 3), (1, 0), (2, 0), (2, 2)) is None


class TestZoneContactWindow:
    def contact(self, w_lo, w_hi, verts=ZONE_VERTS, start=(0, 500), d=(9000, 0)):
        return zone_contact_window(verts, start, d, 1000, 1000, Fraction(w_lo), Fraction(w_hi))

    def test_full_window_matches_first_contact(self):
        assert self.contact(0, 1) == (Fraction(1, 2), 3)

    def test_window_end_touch_counts(self):
        # 窗口终点恰为首触时刻 1/2：闭区间端点相触算碰撞
        assert self.contact(0, Fraction(500000, 1000000)) == (Fraction(1, 2), 3)

    def test_window_start_touch_counts(self):
        assert self.contact(Fraction(500000, 1000000), 1) == (Fraction(1, 2), 3)

    def test_window_start_pushes_collision_time(self):
        # 窗口起于接触区间内部：最早碰撞推迟到窗口起点，责任边按新时刻重估
        got = self.contact(Fraction(700000, 1000000), 1)
        assert got == (Fraction(7, 10), 1)

    def test_window_before_contact_safe(self):
        # 窗口终点 0.499999 早于首触 1/2 → 无碰撞
        assert self.contact(0, Fraction(499999, 1000000)) is None

    def test_window_after_contact_safe(self):
        # 窗口起点 0.722223 晚于末触 13/18 = 0.722222… → 无碰撞
        assert self.contact(Fraction(722223, 1000000), 1) is None

    def test_window_start_one_tick_before_contact_end(self):
        # 窗口起点 0.722222 仍落在接触区间 [1/2, 13/18] 内 → 窗口起点处碰撞
        got = self.contact(Fraction(722222, 1000000), 1)
        assert got is not None
        assert got[0] == Fraction(722222, 1000000)
        assert got[1] == 1

    def test_containment_interval_windowed(self):
        # 矩形全程严格位于区内部（接触区间 [0,1] 来自纯包含）：窗口内最早时刻碰撞，责任边 0
        verts = [(0, 0), (9000, 0), (9000, 9000), (0, 9000)]
        got = zone_contact_window(
            verts, (1000, 1000), (4000, 0), 1000, 1000,
            Fraction(250000, 1000000), Fraction(750000, 1000000),
        )
        assert got == (Fraction(1, 4), 0)

    def test_containment_exit_endpoint(self):
        # 矩形起于区内、t=1/2 完全离区（左缘离区右缘 x=5000）：
        # 窗口 [0.5, 1] 端点相触 → t=1/2，责任边为离区边 1
        verts = [(0, 0), (5000, 0), (5000, 9000), (0, 9000)]
        got = zone_contact_window(
            verts, (1000, 1000), (8000, 0), 1000, 1000,
            Fraction(500000, 1000000), 1,
        )
        assert got == (Fraction(1, 2), 1)

    def test_containment_exit_window_misses(self):
        # 同一几何：窗口起点错开末触时刻 1/2 → 无碰撞
        verts = [(0, 0), (5000, 0), (5000, 9000), (0, 9000)]
        got = zone_contact_window(
            verts, (1000, 1000), (8000, 0), 1000, 1000,
            Fraction(500001, 1000000), 1,
        )
        assert got is None


class TestWindowedFirstCollision:
    def test_no_window_unchanged(self):
        got = first_collision(FLY, [dict(ZONE)])
        assert got == (Fraction(1, 2), "A", 3, 0)

    def test_full_window_matches_no_window(self):
        got = first_collision(FLY, [windowed_zone(0, 1000000)])
        assert got == (Fraction(1, 2), "A", 3, 0)

    def test_window_staggered_safe(self):
        assert first_collision(FLY, [windowed_zone(0, 499999)]) is None

    def test_window_shifts_hit(self):
        got = first_collision(FLY, [windowed_zone(700000, 1000000)])
        assert got == (Fraction(7, 10), "A", 1, 0)

    def test_window_selects_zone(self):
        # 两区同一时刻被撞：A 窗口错开 → 由 B 承担责任
        za = windowed_zone(666667, 1000000, zid="A", verts=[
            {"x": 4000, "y": 1000}, {"x": 5000, "y": 1000},
            {"x": 5000, "y": 2000}, {"x": 4000, "y": 2000},
        ])
        zb = windowed_zone(0, 1000000, zid="B", verts=[
            {"x": 4000, "y": 0}, {"x": 5000, "y": 0},
            {"x": 5000, "y": 1000}, {"x": 4000, "y": 1000},
        ])
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 0}, "end": {"x": 9000, "y": 0}}
        got = first_collision(fly, [zb, za])
        # 矩形下缘与 B 底边共线 → 责任边 0（与无窗口时一致）
        assert got == (Fraction(1, 3), "B", 0, 0)

    def test_tie_break_preserved_when_both_windows_cover(self):
        # 两区窗口均覆盖首触时刻：仍按 id 字典序决胜
        za = windowed_zone(0, 333334, zid="A", verts=[
            {"x": 4000, "y": 1000}, {"x": 5000, "y": 1000},
            {"x": 5000, "y": 2000}, {"x": 4000, "y": 2000},
        ])
        zb = windowed_zone(0, 1000000, zid="B", verts=[
            {"x": 4000, "y": 0}, {"x": 5000, "y": 0},
            {"x": 5000, "y": 1000}, {"x": 4000, "y": 1000},
        ])
        fly = {"width": 1000, "height": 1000, "start": {"x": 0, "y": 0}, "end": {"x": 9000, "y": 0}}
        got = first_collision(fly, [zb, za])
        # 矩形上缘与 A 底边共线 → 责任边 0（与无窗口时一致）
        assert got == (Fraction(1, 3), "A", 0, 1)


# 验收折线：先穿过未启用区 A，随后命中启用区 B
ACCEPT_FLY = {
    "width": 1000, "height": 1000,
    "start": {"x": 0, "y": 3000},
    "waypoints": [{"x": 5000, "y": 3000}],
    "end": {"x": 9000, "y": 3000},
}
# 区 A：第一段几何接触（全程 t∈[0.05, 0.25]），窗口仅覆盖后半程 → 未启用
ACCEPT_ZONE_A = {
    "id": "A",
    "vertices": [
        {"x": 1500, "y": 2500}, {"x": 2500, "y": 2500},
        {"x": 2500, "y": 3500}, {"x": 1500, "y": 3500},
    ],
    "active_window": {"start_tick": 500000, "end_tick": 1000000},
}
# 区 B：第二段几何接触（全程 t∈[0.625, 1]），窗口 [0.6, 0.8] 覆盖首触
ACCEPT_ZONE_B = {
    "id": "B",
    "vertices": [
        {"x": 7000, "y": 2500}, {"x": 9000, "y": 2500},
        {"x": 9000, "y": 3500}, {"x": 7000, "y": 3500},
    ],
    "active_window": {"start_tick": 600000, "end_tick": 800000},
}


def accept_zones(b_window):
    return [
        json.loads(json.dumps(ACCEPT_ZONE_A)),
        dict(json.loads(json.dumps(ACCEPT_ZONE_B)), active_window=b_window),
    ]


class TestSegmentedWindows:
    def test_inactive_then_active_zone(self):
        got = first_collision_segmented(ACCEPT_FLY, accept_zones({"start_tick": 600000, "end_tick": 800000}))
        assert got == (Fraction(5, 8), 1, Fraction(1, 4), "B", 2, 1)

    def test_same_geometry_staggered_windows_safe(self):
        # 相同几何命中：A、B 窗口均错开接触区间 → 全程安全
        got = first_collision_segmented(ACCEPT_FLY, accept_zones({"start_tick": 0, "end_tick": 600000}))
        assert got is None

    def test_window_end_touch_on_segment(self):
        # 窗口终点 0.625 恰为第二段首触时刻 → 端点接触算碰撞
        got = first_collision_segmented(ACCEPT_FLY, accept_zones({"start_tick": 0, "end_tick": 625000}))
        assert got == (Fraction(5, 8), 1, Fraction(1, 4), "B", 2, 1)

    def test_window_pushes_hit_within_segment(self):
        # 窗口起点 0.7 落在第二段接触区间内部 → 全程 t=7/10，段内 t=2/5
        got = first_collision_segmented(ACCEPT_FLY, accept_zones({"start_tick": 700000, "end_tick": 1000000}))
        assert got == (Fraction(7, 10), 1, Fraction(2, 5), "B", 2, 1)

    def test_vertex_attribution_preserved_with_full_window(self):
        # 折点两侧同时命中归前段：全区窗口 [0, 1000000] 不改变归属
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 0},
            "waypoints": [{"x": 4000, "y": 4000}],
            "end": {"x": 0, "y": 8000},
        }
        zone = windowed_zone(0, 1000000, zid="B", verts=[
            {"x": 3000, "y": 5000}, {"x": 4000, "y": 5000},
            {"x": 4000, "y": 6000}, {"x": 3000, "y": 6000},
        ])
        got = first_collision_segmented(fly, [zone])
        assert got == (Fraction(1, 2), 0, Fraction(1), "B", 0, 0)

    def test_vertex_touch_excluded_by_window_falls_to_next_segment(self):
        # 窗口起点错开折点接触（全程 1/2）：后一段接触区间仍与窗口重叠
        # → 窗口起点处碰撞，归后一段
        fly = {
            "width": 1000, "height": 1000,
            "start": {"x": 0, "y": 0},
            "waypoints": [{"x": 4000, "y": 4000}],
            "end": {"x": 0, "y": 8000},
        }
        zone = windowed_zone(500001, 1000000, zid="B", verts=[
            {"x": 3000, "y": 5000}, {"x": 4000, "y": 5000},
            {"x": 4000, "y": 6000}, {"x": 3000, "y": 6000},
        ])
        got = first_collision_segmented(fly, [zone])
        assert got == (Fraction(500001, 1000000), 1, Fraction(1, 500000), "B", 0, 0)


class TestActiveWindowApi:
    def test_hit_echoes_window_and_display(self):
        code, body = post(payload_with(accept_zones({"start_tick": 600000, "end_tick": 800000}),
                                       fly=ACCEPT_FLY))
        assert code == 200
        assert body["collides"] is True
        assert body["zone_id"] == "B"
        assert body["zone_index"] == 1
        assert body["t_fraction"] == "5/8"
        assert body["t_display"] == "0.625000"
        assert body["segment_index"] == 1
        assert body["segment_t_display"] == "0.250000"
        assert body["position_display"] == {"x": "6000", "y": "3000"}
        assert body["active_window"] == {"start_tick": 600000, "end_tick": 800000}
        assert body["active_window_display"] == {"start": "0.600000", "end": "0.800000"}

    def test_window_pushes_hit_response_fields(self):
        code, body = post(payload_with(accept_zones({"start_tick": 700000, "end_tick": 1000000}),
                                       fly=ACCEPT_FLY))
        assert code == 200
        assert body["t_fraction"] == "7/10"
        assert body["t_display"] == "0.700000"
        assert body["segment_t_display"] == "0.400000"
        assert body["position_display"] == {"x": "6600", "y": "3000"}
        assert body["active_window"] == {"start_tick": 700000, "end_tick": 1000000}
        assert body["active_window_display"] == {"start": "0.700000", "end": "1.000000"}

    def test_safe_when_windows_staggered(self):
        code, body = post(payload_with(accept_zones({"start_tick": 0, "end_tick": 600000}),
                                       fly=ACCEPT_FLY))
        assert code == 200
        assert body["collides"] is False
        assert body["active_window"] is None
        assert body["active_window_display"] is None

    def test_legacy_request_window_fields_null(self):
        # 未填写窗口的旧样例：原有字段不变，窗口字段为 null
        code, body = post(payload_with([dict(ZONE)]))
        assert code == 200
        assert body["collides"] is True
        assert body["t_display"] == "0.500000"
        assert body["edge_index"] == 3
        assert body["active_window"] is None
        assert body["active_window_display"] is None

    def test_tick_display_exact_six_decimals(self):
        # 刻度换算为 t 轴展示值：整百万分之一刻度精确到六位
        code, body = post(payload_with(accept_zones({"start_tick": 1, "end_tick": 999999}),
                                       fly=ACCEPT_FLY))
        assert code == 200
        assert body["active_window_display"] == {"start": "0.000001", "end": "0.999999"}


class TestActiveWindowValidation:
    def test_not_an_object(self):
        p = payload_with([dict(ZONE, active_window=[0, 1000000])])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window"

    def test_missing_start_tick(self):
        p = payload_with([dict(ZONE, active_window={"end_tick": 500000})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.start_tick"

    def test_missing_end_tick(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 500000})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.end_tick"

    @pytest.mark.parametrize("bad", [0.5, "500000", True, None])
    def test_non_integer_tick(self, bad):
        p = payload_with([dict(ZONE, active_window={"start_tick": bad, "end_tick": 1000000})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.start_tick"

    def test_negative_start_tick(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": -1, "end_tick": 1000000})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.start_tick"

    def test_start_tick_above_max(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 1000001, "end_tick": 1000001})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.start_tick"

    def test_end_tick_above_max(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 0, "end_tick": 1000001})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.end_tick"

    def test_negative_end_tick(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 0, "end_tick": -1})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.end_tick"

    def test_start_after_end_order_error(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 700000, "end_tick": 300000})])
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.end_tick"

    def test_equal_ticks_accepted(self):
        # 起止相同（单刻窗口）合法；区不在路线上 → 安全
        p = payload_with([dict(ZONE, active_window={"start_tick": 500000, "end_tick": 500000})],
                         fly={"width": 1000, "height": 1000,
                              "start": {"x": 0, "y": 5000}, "end": {"x": 9000, "y": 5000}})
        code, _ = post(p)
        assert code == 200

    def test_boundary_ticks_accepted(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": 0, "end_tick": 1000000})])
        code, body = post(p)
        assert code == 200
        assert body["collides"] is True
        assert body["t_display"] == "0.500000"

    def test_zones_checked_in_order(self):
        # 按禁入区顺序检查：zones.0 合法、zones.1 窗口越界 → 定位 zones.1
        good = dict(ZONE, active_window={"start_tick": 0, "end_tick": 500000})
        bad = dict(json.loads(json.dumps(ZONE)), id="B",
                   active_window={"start_tick": -3, "end_tick": 500000})
        code, body = post(payload_with([good, bad]))
        assert code == 400
        assert body["error"]["path"] == "zones.1.active_window.start_tick"

    def test_vertices_error_precedes_window_error(self):
        # 同一禁入区内先校验 vertices（文档顺序），再校验 active_window
        bad = {"id": "A", "vertices": [{"x": 0, "y": 0}, {"x": 100, "y": 0}],
               "active_window": {"start_tick": -1, "end_tick": -2}}
        code, body = post(payload_with([bad]))
        assert code == 400
        assert body["error"]["path"] == "zones.0.vertices"

    def test_fly_error_precedes_window_error(self):
        p = payload_with([dict(ZONE, active_window={"start_tick": -1, "end_tick": -2})])
        del p["fly"]["start"]["x"]
        code, body = post(p)
        assert code == 400
        assert body["error"]["path"] == "fly.start.x"

    def test_long_integer_tick_located(self):
        big = "9" * 5000
        text = (
            '{"stage":{"width":10000,"height":10000},'
            '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},"end":{"x":1000,"y":0}},'
            '"zones":[{"id":"A","vertices":[{"x":0,"y":0},{"x":10,"y":0},{"x":0,"y":10}],'
            '"active_window":{"start_tick":%s,"end_tick":1000000}}]}' % big
        )
        code, body = post(text)
        assert code == 400
        assert body["error"]["path"] == "zones.0.active_window.start_tick"

    def test_validate_returns_window(self):
        data = validate(payload_with([windowed_zone(250000, 750000)]))
        assert data["zones"][0]["active_window"] == {"start_tick": 250000, "end_tick": 750000}

    def test_validate_without_window_returns_none(self):
        data = validate(payload_with([dict(ZONE)]))
        assert data["zones"][0]["active_window"] is None
