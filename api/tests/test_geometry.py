"""几何核心：连续扫掠判定的临界值测试（精确 Fraction 校验）。

责任边约定：顶点接触同时计入该顶点的两条相邻边，决胜时取较小边序号。
"""

from fractions import Fraction

from app.geometry import (
    first_collision,
    point_segment_first_t,
    point_strictly_in_polygon,
    segments_intersect,
    zone_first_contact,
)

SQUARE_CCW = [(4000, 500), (6000, 500), (6000, 1500), (4000, 1500)]
# 上下边超出矩形行程高度的测试区：y∈[0,2000]
TALL = [(4000, 0), (6000, 0), (6000, 2000), (4000, 2000)]


def fly(start, end, w=1000, h=1000):
    return {
        "width": w,
        "height": h,
        "start": {"x": start[0], "y": start[1]},
        "end": {"x": end[0], "y": end[1]},
    }


def zone(zid, verts):
    return {"id": zid, "vertices": [{"x": x, "y": y} for x, y in verts]}


class TestPointSegment:
    def test_crossing_hit(self):
        # 点 (0,1) 以速度 (4,0) 运动，线段 x=2, y∈[0,2] → t=1/2
        t = point_segment_first_t((0, 1), (4, 0), (2, 0), (2, 2))
        assert t == Fraction(1, 2)

    def test_miss_beyond_segment_end(self):
        t = point_segment_first_t((0, 3), (1, 0), (2, 0), (2, 2))
        assert t is None

    def test_collinear_enter_interval(self):
        # 点沿线段所在直线滑动，t∈[1/4,1/2] 位于线段上
        t = point_segment_first_t((0, 0), (8, 0), (2, 0), (4, 0))
        assert t == Fraction(1, 4)

    def test_collinear_already_on(self):
        t = point_segment_first_t((3, 0), (1, 0), (2, 0), (4, 0))
        assert t == Fraction(0)

    def test_collinear_static_on_segment(self):
        t = point_segment_first_t((3, 0), (0, 0), (2, 0), (4, 0))
        assert t == Fraction(0)

    def test_parallel_never(self):
        t = point_segment_first_t((0, 1), (1, 0), (2, 0), (4, 0))
        assert t is None

    def test_negative_t_rejected(self):
        t = point_segment_first_t((5, 1), (1, 0), (2, 0), (2, 2))
        assert t is None

    def test_endpoint_touch_counts(self):
        t = point_segment_first_t((0, 0), (4, 0), (2, 0), (2, 2))
        assert t == Fraction(1, 2)


class TestStaticPredicates:
    def test_segments_intersect_cross(self):
        assert segments_intersect((0, 0), (4, 4), (0, 4), (4, 0))

    def test_segments_intersect_touch_endpoint(self):
        assert segments_intersect((0, 0), (2, 0), (2, 0), (2, 2))

    def test_segments_intersect_collinear_overlap(self):
        assert segments_intersect((0, 0), (4, 0), (2, 0), (6, 0))

    def test_segments_disjoint(self):
        assert not segments_intersect((0, 0), (1, 0), (0, 1), (1, 1))

    def test_point_in_polygon(self):
        assert point_strictly_in_polygon((5000, 1000), SQUARE_CCW)
        assert not point_strictly_in_polygon((0, 0), SQUARE_CCW)

    def test_point_on_boundary_not_strict(self):
        assert not point_strictly_in_polygon((4000, 1000), SQUARE_CCW)


class TestZoneFirstContact:
    def test_head_on_edge_hit(self):
        # 矩形 y∈[500,1500] 右行，右缘撞上区左缘 x=4000（y∈[0,2000]）内部
        # → t=1/3，仅边 3 接触
        got = zone_first_contact(TALL, (0, 500), (9000, 0), 1000, 1000)
        assert got == (Fraction(1, 3), 3)

    def test_vertex_contact_takes_smaller_edge(self):
        # 矩形下缘与区底边共线（y=0）：右下角撞上区左下顶点 → 相邻边 0 与 3，取 0
        got = zone_first_contact(TALL, (0, 0), (9000, 0), 1000, 1000)
        assert got == (Fraction(1, 3), 0)

    def test_diagonal_exact_fraction(self):
        # 右缘 x=9000t+1000 触 x=5000 → t=4/9；接触点含区左上顶点 → 边 2、3 取 2
        verts = [(5000, 0), (7000, 0), (7000, 2000), (5000, 2000)]
        got = zone_first_contact(verts, (0, 0), (9000, 3000), 1000, 1000)
        assert got == (Fraction(4, 9), 2)

    def test_collinear_slide_entry(self):
        # 矩形上缘 y=1000 与区底边共线，进入重叠区间首端 t=2/5
        verts = [(3000, 1000), (4000, 1000), (4000, 2000), (3000, 2000)]
        got = zone_first_contact(verts, (0, 0), (5000, 0), 1000, 1000)
        assert got == (Fraction(2, 5), 0)

    def test_touch_at_t_zero(self):
        # 起始即贴边：矩形右缘 x=1000 贴区左缘 x=1000；角点落在边 0 端点上 → 边 0
        verts = [(1000, 0), (3000, 0), (3000, 1000), (1000, 1000)]
        got = zone_first_contact(verts, (0, 0), (5000, 0), 1000, 1000)
        assert got == (Fraction(0), 0)

    def test_touch_at_t_one(self):
        # 终点恰好接触：end=(3000,500)，右缘 x=4000 触区左缘内部 → t=1，边 3
        got = zone_first_contact(TALL, (0, 500), (3000, 0), 1000, 1000)
        assert got == (Fraction(1), 3)

    def test_no_collision_passes_above(self):
        got = zone_first_contact(SQUARE_CCW, (0, 2000), (9000, 0), 1000, 1000)
        assert got is None

    def test_zero_motion_overlap(self):
        # 静止矩形 [4500,5500]×[750,1750] 与区相交：仅区顶边（边 2）被跨
        got = zone_first_contact(SQUARE_CCW, (4500, 750), (0, 0), 1000, 1000)
        assert got == (Fraction(0), 2)

    def test_zero_motion_clear(self):
        got = zone_first_contact(SQUARE_CCW, (0, 0), (0, 0), 1000, 1000)
        assert got is None

    def test_strictly_inside_at_start_edge_zero(self):
        # 矩形严格位于区内部且不接触边 → t=0，责任边规定为 0
        verts = [(0, 0), (9000, 0), (9000, 9000), (0, 9000)]
        got = zone_first_contact(verts, (1000, 1000), (4000, 4000), 1000, 1000)
        assert got == (Fraction(0), 0)

    def test_zone_strictly_inside_rect_at_start(self):
        # 区严格位于矩形内部 → t=0，责任边 0
        verts = [(200, 200), (300, 200), (300, 300), (200, 300)]
        got = zone_first_contact(verts, (0, 0), (0, 0), 1000, 1000)
        assert got == (Fraction(0), 0)

    def test_crossing_overlap_at_t_zero(self):
        # 区边 x=2500 横穿静止矩形 [2000,3000]²（无顶点落在对方边上/内部）
        verts = [(2500, 1000), (2500, 4000), (3500, 2500)]
        got = zone_first_contact(verts, (2000, 2000), (0, 0), 1000, 1000)
        assert got == (Fraction(0), 0)


class TestFirstCollision:
    def test_tie_break_zone_id_lexicographic(self):
        # 两区同一时刻被撞：取 id 字典序较小者
        za = zone("A", [(4000, 1000), (5000, 1000), (5000, 2000), (4000, 2000)])
        zb = zone("B", [(4000, 0), (5000, 0), (5000, 1000), (4000, 1000)])
        got = first_collision(fly((0, 0), (9000, 0)), [zb, za])
        assert got is not None
        t, zid, edge, _ = got
        assert t == Fraction(1, 3)
        assert zid == "A"
        assert edge == 0

    def test_tie_break_edge_index(self):
        # 同一区两边同时接触（顶点撞边）：取边序号较小者
        got = first_collision(fly((0, 0), (9000, 0)), [zone("Z", TALL)])
        assert got is not None
        assert got[0] == Fraction(1, 3)
        assert got[2] == 0

    def test_inside_zone_competes_with_touch_zone(self):
        # t=0：矩形贴 A 右缘（边 1），同时严格位于 B 内（责任边规定为 0）
        # 同 t=0，按 id 字典序决胜 → A
        za = zone("A", [(0, 0), (2000, 0), (2000, 2000), (0, 2000)])
        zb = zone("B", [(1000, 0), (9000, 0), (9000, 9000), (1000, 9000)])
        got = first_collision(fly((2000, 500), (2000, 500)), [zb, za])
        assert got is not None
        t, zid, edge, _ = got
        assert t == 0
        assert zid == "A"
        assert edge == 1

    def test_no_zones_no_collision(self):
        assert first_collision(fly((0, 0), (9000, 0)), []) is None

    def test_position_fraction(self):
        # 碰撞位置 = start + t·d，此处校验 t 精确值
        verts = [(5000, 0), (7000, 0), (7000, 2000), (5000, 2000)]
        got = first_collision(fly((0, 0), (9000, 3000)), [zone("Z", verts)])
        assert got is not None
        t = got[0]
        assert t == Fraction(4, 9)
        assert 0 + t * 9000 == 4000
        assert t * 3000 == Fraction(4000, 3)
