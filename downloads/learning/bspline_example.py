#!/usr/bin/env python3
"""复算《B 样条：一步一步看懂控制点的局部作用》。

只使用 Python 标准库。运行：python bspline_example.py
模型：未夹持三次均匀 B 样条，9 个控制点、6 段、每段 2 秒。
"""
from __future__ import annotations

import math
from typing import Sequence

Point = tuple[float, float]
POINTS: tuple[Point, ...] = (
    (-2., 0.), (0., 0.), (2., 0.), (4., 3.), (6., 3.),
    (8., 3.), (10., 0.), (12., 0.), (14., 0.),
)
KNOTS = tuple(float(k) for k in range(-3, 10))
SPAN_TIME = 2.0


def validate(points: Sequence[Point], duration: float = SPAN_TIME) -> None:
    if len(points) < 4:
        raise ValueError('三次曲线至少需要四个控制点。')
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('每段时间必须是正的有限数。')
    if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError('控制点必须是有限的二维坐标。')


def weighted(points: Sequence[Point], weights: Sequence[float]) -> Point:
    if len(points) != len(weights):
        raise ValueError('权重与控制点数量不一致。')
    return tuple(sum(w * p[d] for w, p in zip(weights, points))
                 for d in range(2))  # type: ignore[return-value]


def segment_coefficients(points: Sequence[Point], i: int) -> tuple[Point, ...]:
    """返回 C_i(s) 的常数项至三次项，每项是二维向量。"""
    validate(points)
    if not isinstance(i, int) or not 0 <= i < len(points) - 3:
        raise ValueError('曲线段编号越界。')
    active = points[i:i + 4]
    return tuple(weighted(active, row) for row in (
        (1/6, 4/6, 1/6, 0), (-1/2, 0, 1/2, 0),
        (1/2, -1, 1/2, 0), (-1/6, 1/2, -1/2, 1/6),
    ))


def segment(points: Sequence[Point], i: int, s: float,
            derivative: int = 0, duration: float = SPAN_TIME) -> Point:
    """求本段位置，或对实际时间的一至三阶导数。"""
    validate(points, duration)
    if derivative not in (0, 1, 2, 3):
        raise ValueError('导数次数应为 0、1、2 或 3。')
    if not math.isfinite(s) or not 0 <= s <= 1:
        raise ValueError('本段参数必须在 [0,1] 内。')
    coeff = segment_coefficients(points, i)
    weights = [0. if k < derivative else
               math.factorial(k) / math.factorial(k - derivative)
               * s ** (k - derivative) / duration ** derivative
               for k in range(4)]
    return weighted(coeff, weights)


def evaluate(points: Sequence[Point], t: float, derivative: int = 0,
             duration: float = SPAN_TIME) -> Point:
    """在整条轨迹上查询；连接处取右段，终点取末段的 s=1。"""
    validate(points, duration)
    count = len(points) - 3
    if not math.isfinite(t) or not 0 <= t <= count * duration:
        raise ValueError('时间超出轨迹范围。')
    u = t / duration
    i = min(int(math.floor(u)), count - 1)
    return segment(points, i, u - i, derivative, duration)


def local_bezier(points: Sequence[Point], i: int) -> tuple[Point, ...]:
    """同一 B 样条段的四个等价 Bézier 控制点。"""
    segment_coefficients(points, i)  # 验证编号及输入
    q = points[i:i + 4]
    return tuple(weighted(q, w) for w in (
        (1/6, 4/6, 1/6, 0), (0, 2/3, 1/3, 0),
        (0, 1/3, 2/3, 0), (0, 1/6, 4/6, 1/6),
    ))


def bezier(points: Sequence[Point], s: float) -> Point:
    return weighted(points, ((1-s)**3, 3*(1-s)**2*s,
                             3*(1-s)*s*s, s**3))


def basis(i: int, degree: int, u: float, knots: Sequence[float]) -> float:
    """Cox–de Boor 递推，用于独立核验文中的局部公式。"""
    if degree == 0:
        return float(knots[i] <= u < knots[i + 1])
    left_den = knots[i + degree] - knots[i]
    right_den = knots[i + degree + 1] - knots[i + 1]
    left = ((u - knots[i]) / left_den * basis(i, degree - 1, u, knots)
            if left_den else 0.)
    right = ((knots[i + degree + 1] - u) / right_den
             * basis(i + 1, degree - 1, u, knots) if right_den else 0.)
    return left + right


def derivative_bounds(points: Sequence[Point], duration: float = SPAN_TIME):
    """通过相邻控制点的一阶、二阶差，得到全区间充分上界。"""
    validate(points, duration)
    velocity_controls = [tuple((b[d] - a[d]) / duration for d in range(2))
                         for a, b in zip(points, points[1:])]
    acceleration_controls = [
        tuple((points[i][d] - 2*points[i+1][d] + points[i+2][d])
              / duration**2 for d in range(2))
        for i in range(len(points) - 2)]
    return (max(math.hypot(*v) for v in velocity_controls),
            max(math.hypot(*a) for a in acceleration_controls))


def verify_geometry(points: Sequence[Point]) -> None:
    """用整段凸包证明避开 [5,7]×[0,2]，而非用采样代替安全验证。"""
    eps = 1e-10
    for i in range(6):
        q = local_bezier(points, i)
        assert all(-3-eps <= x <= 15+eps and -1-eps <= y <= 6+eps for x,y in q)
        if i <= 1:
            assert max(x for x, y in q) <= 4 + eps < 5
        elif i >= 4:
            assert min(x for x, y in q) >= 8 - eps > 7
        else:
            assert all(4-eps <= x <= 8+eps and 2.5-eps <= y <= 4.5+eps
                       for x,y in q)


def assert_vector_close(a: Point, b: Point, tol: float = 1e-9) -> None:
    assert all(math.isclose(x,y,abs_tol=tol,rel_tol=tol) for x,y in zip(a,b)), (a,b)


def main() -> None:
    changed = list(POINTS)
    changed[4] = (6., 4.5)
    for points in (POINTS, changed):
        for i in range(6):
            for s in (0., .25, .5, .75, 1.):
                p = segment(points, i, s)
                assert_vector_close(p, bezier(local_bezier(points,i), s))
                # 独立使用完整节点向量验证标准 B 样条基函数。
                u = i + s
                weights = [basis(j,3,u,KNOTS) for j in range(9)]
                assert math.isclose(sum(weights),1.,abs_tol=1e-10)
                assert_vector_close(p, weighted(points,weights))
        for i in range(5):
            for order in range(3):
                assert_vector_close(segment(points,i,1.,order),
                                    segment(points,i+1,0.,order))
        verify_geometry(points)
        vbound, abound = derivative_bounds(points)
        assert vbound <= 2 and abound <= 1

    # 未受影响的两段，四个多项式系数完全相同。
    for i in (0,5):
        for a,b in zip(segment_coefficients(POINTS,i),segment_coefficients(changed,i)):
            assert_vector_close(a,b)
    for order in range(3):
        for t in (0.,12.):
            assert_vector_close(evaluate(POINTS,t,order),evaluate(changed,t,order))

    print('第二段的等价 Bézier 控制点：')
    for q in local_bezier(POINTS,1):
        print(' ',tuple(round(x,6) for x in q))
    print('\n第 3 秒：')
    for order,label in enumerate(('位置','速度','加速度')):
        print(f'  {label}：{evaluate(POINTS,3.,order)}')
    print('\n第 4 秒左右两侧：')
    for order,label in enumerate(('位置','速度','加速度','Jerk')):
        print(f'  {label}：左 {segment(POINTS,1,1.,order)}；右 {segment(POINTS,2,0.,order)}')
    print('\n移动 P4 后的纵向位置变化：')
    for t,expect in ((1,0),(3,1/32),(5,23/32),(6,1),(7,23/32),(9,1/32),(11,0)):
        old,new=evaluate(POINTS,float(t)),evaluate(changed,float(t))
        assert math.isclose(new[1]-old[1],expect,abs_tol=1e-9)
        print(f'  t={t:2d}：原 y={old[1]:.5f}；新 y={new[1]:.5f}；变化={new[1]-old[1]:.5f}')
    print('\n全区间速度、加速度充分上界：')
    for label,points in (('原曲线',POINTS),('修改后',changed)):
        print(f'  {label}：{derivative_bounds(points)}')
    print('\n全部核验通过：标准基函数、局部 Bézier 等价、C2 衔接、局部作用、边界状态、整段凸包避障和运动上界。')


if __name__ == '__main__':
    main()
