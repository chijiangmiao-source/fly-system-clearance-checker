"""双吊景交会分析（独立模块）。

两套编号不同的吊景（轴对齐矩形，各自带尺寸与折线路线）在同一总时长
t∈[0,1] 内等时运行：每个吊景的所有分段耗时相等，段内匀速。判定两矩形
全程是否接触（边界接触也算冲突），并求全程最早冲突时刻及当时双方所在
段号、双方姿态与接触位置。

共同时间轴按双方折点时刻（i/n 与 j/m）的并集切分；每个小区间内双方各自
位于固定分段，矩形在 x、y 两个轴向上的边界坐标都是 t 的仿射函数。两个
轴对齐闭矩形相交当且仅当两个移动区间在 x、y 轴上同时相交：每个轴的相交
时刻集是一个闭区间（相对位置为仿射函数），两轴区间相交即发生接触，取
交集左端为该小区间的首次接触时刻。全程使用 Fraction 精确求解。
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import List, Optional, Sequence, Tuple

Point = Tuple[int, int]

_ZERO = Fraction(0)
_ONE = Fraction(1)


def route_points(fly: dict) -> List[Point]:
    """吊景折线路线的全部顶点：start → 各停位 → end。"""
    pts: List[Point] = [(fly["start"]["x"], fly["start"]["y"])]
    for wp in fly.get("waypoints") or []:
        pts.append((wp["x"], wp["y"]) if isinstance(wp, dict) else wp)
    end = fly["end"]
    pts.append((end["x"], end["y"]) if isinstance(end, dict) else end)
    return pts


def breakpoints(n: int, m: int) -> List[Fraction]:
    """双方折点时刻 {i/n}∪{j/m} 的严格递增序列（含 0、1）。"""
    marks = {Fraction(i, n) for i in range(n + 1)}
    marks.update(Fraction(j, m) for j in range(m + 1))
    return sorted(marks)


def _axis_motion(
    points: Sequence[Point], seg: int, nseg: int, axis: int
) -> Tuple[int, int]:
    """该吊景位于第 seg 段时，指定轴（0=x,1=y）左下角坐标关于 t 的仿射系数。

    段内参数 u = nseg·t − seg，左下角坐标 = p_seg + u·(p_seg+1 − p_seg)
    = nseg·Δ·t + (p_seg − seg·Δ)，返回 (nseg·Δ, p_seg − seg·Δ)。
    """
    delta = points[seg + 1][axis] - points[seg][axis]
    return nseg * delta, points[seg][axis] - seg * delta


def _axis_overlap_window(
    va: int, ca: int, sa: int, vb: int, cb: int, sb: int,
    t0: Fraction, t1: Fraction,
) -> Optional[Tuple[Fraction, Fraction]]:
    """一个轴向上两移动区间相交的时刻窗口（与小区间 [t0,t1] 取交后）。

    吊景 k 的区间为 [v_k·t + c_k, v_k·t + c_k + s_k]（s_k 为该轴尺寸）。
    令相对位置 d(t) = (v_b−v_a)·t + (c_b−c_a)，闭区间相交当且仅当
    −s_b ≤ d(t) ≤ s_a；d 为仿射函数，解集是单个闭区间。
    无交集返回 None。
    """
    vd = vb - va
    bd = cb - ca
    enter = t0
    exit_ = t1
    if vd == 0:
        if not (-sb <= bd <= sa):
            return None
        return enter, exit_
    # d(t) ≤ s_a
    r_hi = Fraction(sa - bd, vd)
    # d(t) ≥ −s_b  ⇔  d(t) 的另一侧根
    r_lo = Fraction(-sb - bd, vd)
    if vd > 0:  # d 随 t 增大：r_lo 为进入时刻，r_hi 为离开时刻
        win_lo, win_hi = r_lo, r_hi
    else:  # d 随 t 减小：从 r_hi 端进入，向 r_lo 端离开
        win_lo, win_hi = r_hi, r_lo
    if win_lo > enter:
        enter = win_lo
    if win_hi < exit_:
        exit_ = win_hi
    if enter > exit_:
        return None
    return enter, exit_


def encounter_first_contact(fly_a: dict, fly_b: dict):
    """两个轴对齐矩形吊景的全程首次接触。

    返回 (全程 t, a 段号, a 段内 t, b 段号, b 段内 t,
          (a 左下点, b 左下点, 接触点))；坐标与时刻均为 Fraction。
    全程无接触返回 None。

    折点两侧同时命中（前段段内 t=1 与后段段内 t=0）归前段：小区间自左向右
    扫描，全程时刻严格更小时才替换，故同一时刻由左侧（前段）小区间胜出。
    """
    wa, ha = fly_a["width"], fly_a["height"]
    wb, hb = fly_b["width"], fly_b["height"]
    pa = route_points(fly_a)
    pb = route_points(fly_b)
    n, m = len(pa) - 1, len(pb) - 1
    marks = breakpoints(n, m)

    best: Optional[Tuple[Fraction, int, int]] = None  # (t, a 段号, b 段号)
    for k in range(len(marks) - 1):
        t0, t1 = marks[k], marks[k + 1]
        # 小区间左端点处双方所在段号（折点右侧段；恰在折点接触时由左侧
        # 相邻小区间以其右端点先命中，严格比较下归前段）
        ia = math.floor(t0 * n)
        ib = math.floor(t0 * m)

        avx, acx = _axis_motion(pa, ia, n, 0)
        avy, acy = _axis_motion(pa, ia, n, 1)
        bvx, bcx = _axis_motion(pb, ib, m, 0)
        bvy, bcy = _axis_motion(pb, ib, m, 1)

        win_x = _axis_overlap_window(avx, acx, wa, bvx, bcx, wb, t0, t1)
        if win_x is None:
            continue
        win_y = _axis_overlap_window(avy, acy, ha, bvy, bcy, hb, t0, t1)
        if win_y is None:
            continue
        enter = win_x[0] if win_x[0] > win_y[0] else win_y[0]
        exit_ = win_x[1] if win_x[1] < win_y[1] else win_y[1]
        if enter > exit_:
            continue
        if best is None or enter < best[0]:
            best = (enter, ia, ib)

    if best is None:
        return None

    t, ia, ib = best
    # 双方姿态（左下角）与段内时刻
    ua, ub = t * n - ia, t * m - ib
    ax = pa[ia][0] + ua * (pa[ia + 1][0] - pa[ia][0])
    ay = pa[ia][1] + ua * (pa[ia + 1][1] - pa[ia][1])
    bx = pb[ib][0] + ub * (pb[ib + 1][0] - pb[ib][0])
    by = pb[ib][1] + ub * (pb[ib + 1][1] - pb[ib][1])
    # 接触点：接触瞬间两矩形交集矩形的中心（边/面接触时为接触面段中点）
    contact_x = (max(ax, bx) + min(ax + wa, bx + wb)) / 2
    contact_y = (max(ay, by) + min(ay + ha, by + hb)) / 2
    return (
        t,
        ia,
        ua,
        ib,
        ub,
        ((ax, ay), (bx, by), (contact_x, contact_y)),
    )
