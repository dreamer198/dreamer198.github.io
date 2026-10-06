#!/usr/bin/env python3
"""复算《安全飞行走廊：一步一步把避障区域写进轨迹优化》。

只使用 Python 标准库。用精确分数求解两个必要约束组成的放松问题，
再核验全部走廊、导数控制向量和边界状态；候选通过全部核验后，
它同时也是正文完整问题的最优解。

运行：python safe_corridor_example.py
可选：python safe_corridor_example.py --json verified.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from fractions import Fraction as F
from pathlib import Path
from typing import Sequence

Vector = tuple[F, F]
H = F(2)  # 每段时间（秒）
D = (
    (1, 0, 0), (-3, 1, 0), (3, -3, 1),
    (-1, 3, -3), (0, -1, 3), (0, 0, -1),
)
# J = q^T M q / 32，故 Hessian = M / 16。
M = ((20, -15, 6), (-15, 20, -15), (6, -15, 20))
HESSIAN = tuple(tuple(F(v, 16) for v in row) for row in M)
# 必要条件 4a+b>=15、b+4c>=15 写成 G q<=rhs。
G = ((F(-4), F(-1), F(0)), (F(0), F(-1), F(-4)))
RHS = (F(-15), F(-15))
REGIONS = (
    (F(0), F(9, 2), F(0), F(9, 2)),
    (F(4), F(8), F(5, 2), F(9, 2)),
    (F(15, 2), F(12), F(0), F(9, 2)),
)
SPAN_REGION = (0, 0, 1, 1, 2, 2)
OBSTACLE = (F(5), F(7), F(0), F(2))


def dot(a: Sequence, b: Sequence):
    return sum(x * y for x, y in zip(a, b))


def linear_solve(matrix: Sequence[Sequence], rhs: Sequence) -> tuple[F, ...]:
    """带主元选择的精确高斯消元，避免通过显式求逆求解。"""
    n = len(rhs)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("线性系统必须为方阵，且维数与右端项一致。")
    aug = [[F(v) for v in row] + [F(rhs[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if aug[pivot][col] == 0:
            raise ValueError("线性系统奇异。")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        divisor = aug[col][col]
        aug[col] = [v / divisor for v in aug[col]]
        for row in range(n):
            if row != col:
                factor = aug[row][col]
                aug[row] = [v - factor * w for v, w in zip(aug[row], aug[col])]
    return tuple(aug[i][-1] for i in range(n))


def cost(q: Sequence):
    return sum(dot(row, q) ** 2 for row in D) / 32


def gradient(q: Sequence):
    return tuple(dot(row, q) for row in HESSIAN)


def solve_relaxed_qp():
    """枚举这两个不等式的有效约束组合，独立核对正文手算。"""
    solutions = []
    for count in range(3):
        for active in itertools.combinations(range(2), count):
            n = 3 + count
            matrix = [[F(0) for _ in range(n)] for _ in range(n)]
            rhs = [F(0)] * n
            for i in range(3):
                for j in range(3):
                    matrix[i][j] = HESSIAN[i][j]
            for k, index in enumerate(active):
                for j in range(3):
                    matrix[j][3 + k] = G[index][j]
                    matrix[3 + k][j] = G[index][j]
                rhs[3 + k] = RHS[index]
            try:
                ans = linear_solve(matrix, rhs)
            except ValueError:
                continue
            q, multipliers = ans[:3], ans[3:]
            if any(dot(row, q) > r for row, r in zip(G, RHS)):
                continue
            if any(value < 0 for value in multipliers):
                continue
            solutions.append((cost(q), q, active, multipliers))
    if not solutions:
        raise RuntimeError("放松问题未找到可行最优候选。")
    return min(solutions, key=lambda item: item[0])


def controls(q: Sequence) -> tuple[Vector, ...]:
    a, b, c = map(F, q)
    y = (F(0), F(0), F(0), a, b, c, F(0), F(0), F(0))
    return tuple((F(2 * i - 2), y[i]) for i in range(9))


def blend(points: Sequence[Vector], weights: Sequence) -> Vector:
    return tuple(sum(F(w) * p[k] for w, p in zip(weights, points)) for k in range(2))


def local_bezier(points: Sequence[Vector], i: int) -> tuple[Vector, ...]:
    p = points[i:i + 4]
    return (
        blend(p, (F(1, 6), F(4, 6), F(1, 6), 0)),
        blend(p, (0, F(2, 3), F(1, 3), 0)),
        blend(p, (0, F(1, 3), F(2, 3), 0)),
        blend(p, (0, F(1, 6), F(4, 6), F(1, 6))),
    )


def evaluate_span(points: Sequence[Vector], i: int, s, order=0) -> Vector:
    """s 为各段局部参数；返回对实际时间的 order 阶导数。"""
    s = F(s)
    if not 0 <= i < 6 or not 0 <= s <= 1 or order not in (0, 1, 2, 3):
        raise ValueError("段编号、局部参数或导数阶数无效。")
    if order == 0:
        w = ((1-s)**3/6, (3*s**3-6*s**2+4)/6,
             (-3*s**3+3*s**2+3*s+1)/6, s**3/6)
    elif order == 1:
        w = (-(1-s)**2/2, F(3, 2)*s*s-2*s,
             -F(3, 2)*s*s+s+F(1, 2), s*s/2)
    elif order == 2:
        w = (1-s, 3*s-2, 1-3*s, s)
    else:
        w = (-1, 3, -3, 1)
    return blend(points[i:i+4], tuple(value/H**order for value in w))


def evaluate(points: Sequence[Vector], t, order=0) -> Vector:
    t = F(t)
    if not 0 <= t <= 12:
        raise ValueError("总时间必须位于 [0,12]。")
    i = min(5, int(t // H))
    return evaluate_span(points, i, (t - i*H)/H, order)


def derivative_vectors(points: Sequence[Vector]):
    first = tuple(tuple((points[i+1][k]-points[i][k])/H for k in range(2))
                  for i in range(8))
    second = tuple(tuple((points[i][k]-2*points[i+1][k]+points[i+2][k])/H**2
                         for k in range(2)) for i in range(7))
    return first, second


def geometry_valid(points: Sequence[Vector]) -> bool:
    for i in range(6):
        xmin, xmax, ymin, ymax = REGIONS[SPAN_REGION[i]]
        for x, y in local_bezier(points, i):
            if not (xmin <= x <= xmax and ymin <= y <= ymax):
                return False
    return True


def verify(points: Sequence[Vector]):
    # 对有限个控制向量的核验，给出全区间的证明；不靠离散取样证明安全。
    if not geometry_valid(points):
        raise ValueError("至少一段的 Bézier 控制点未满足指定走廊。")
    for xmin, xmax, ymin, ymax in REGIONS:
        ox0, ox1, oy0, oy1 = OBSTACLE
        assert xmax < ox0 or xmin > ox1 or ymax < oy0 or ymin > oy1
        assert -3 <= xmin <= xmax <= 15 and -1 <= ymin <= ymax <= 6
    first, second = derivative_vectors(points)
    speed_sq_bound = max(dot(d, d) for d in first)
    accel_sq_bound = max(dot(e, e) for e in second)
    if speed_sq_bound > 4 or accel_sq_bound > 1:
        raise ValueError("导数控制向量未通过本例运动上界。")
    for i in range(5):
        for order in range(3):
            assert evaluate_span(points, i, 1, order) == evaluate_span(points, i+1, 0, order)
    for t, target in [(0, (F(0), F(0))), (12, (F(12), F(0)))]:
        assert evaluate(points, t) == target
        assert evaluate(points, t, 1) == (F(1), F(0))
        assert evaluate(points, t, 2) == (F(0), F(0))
    # 用另一套 Bernstein 计算核对局部转换。
    for i in range(6):
        bezier = local_bezier(points, i)
        for s in (F(0), F(1, 4), F(1, 2), F(3, 4), F(1)):
            weights = ((1-s)**3, 3*(1-s)**2*s, 3*(1-s)*s*s, s**3)
            assert blend(bezier, weights) == evaluate_span(points, i, s)
    integral = sum(H*dot(evaluate_span(points, i, F(1, 2), 3),
                         evaluate_span(points, i, F(1, 2), 3)) for i in range(6))
    q = (points[3][1], points[4][1], points[5][1])
    assert integral == cost(q)
    return speed_sq_bound, accel_sq_bound


def exact_speed_peak(points: Sequence[Vector]):
    # vx恒为1，每段vy是二次式。检查端点及a_y=0的位置即可得到最大速度。
    candidates = []
    _, e = derivative_vectors(points)
    for i in range(6):
        local = {F(0), F(1)}
        if e[i+1][1] != e[i][1]:
            s = -e[i][1] / (e[i+1][1] - e[i][1])
            if 0 < s < 1:
                local.add(s)
        for s in local:
            velocity = evaluate_span(points, i, s, 1)
            candidates.append((dot(velocity, velocity), i*H+s*H))
    sq, t = max(candidates)
    return math.sqrt(float(sq)), float(t)


def fmt_vector(values: Sequence) -> str:
    return '(' + ', '.join(f'{float(v):.6f}' for v in values) + ')'


def make_report():
    optimal_cost, q, active, multipliers = solve_relaxed_qp()
    expected = (F(275,102), F(215,51), F(275,102))
    assert q == expected
    assert optimal_cost == F(875,544)
    assert active == (0, 1) and multipliers == (F(175,1632), F(175,1632))
    # 从平方和结构独立检查严格凸性：D 的前三行呈可逆三角结构。
    # a=0，b-3a=0，c-3b+3a=0 同时为0必推出q=0。
    for row in range(3):
        assert all(HESSIAN[row][col] ==
                   sum(F(r[row]*r[col],16) for r in D) for col in range(3))
    # 用双边差分核验代价梯度（仅作数值交叉检查）。
    eps = 1e-5
    qf = list(map(float, q))
    for i in range(3):
        plus, minus = qf[:], qf[:]
        plus[i] += eps; minus[i] -= eps
        fd = (cost(plus) - cost(minus)) / (2*eps)
        assert abs(fd - float(gradient(q)[i])) < 1e-7

    cases = {}
    for name, values in [('initial', (F(3),)*3), ('optimized', q)]:
        p = controls(values)
        vsq, asq = verify(p)
        actual_peak, peak_time = exact_speed_peak(p)
        first, second = derivative_vectors(p)
        cases[name] = {
            'variables': list(map(float, values)),
            'controls': [list(map(float, item)) for item in p],
            'cost': float(cost(values)),
            'bezier': [[list(map(float, item)) for item in local_bezier(p,i)] for i in range(6)],
            'velocity_vectors': [list(map(float, item)) for item in first],
            'acceleration_vectors': [list(map(float, item)) for item in second],
            'speed_bound': math.sqrt(float(vsq)),
            'acceleration_bound': math.sqrt(float(asq)),
            'speed_peak': actual_peak, 'speed_peak_time': peak_time,
            'samples': [{'t': t, 'p': list(map(float,evaluate(p,t))),
                         'v': list(map(float,evaluate(p,t,1))),
                         'a': list(map(float,evaluate(p,t,2)))}
                        for t in [0,2,4,5,6,7,8,10,12]],
        }
    assert not geometry_valid(controls((0,0,0)))
    # 此例能够满足走廊，但中点加速度为-1.05，运动约束将其排除。
    assert geometry_valid(controls((3,F(51,10),3)))
    try:
        verify(controls((3,F(51,10),3)))
    except ValueError:
        pass
    else:
        raise AssertionError('测试候选应被加速度约束拒绝。')
    return {'h':2, 'duration':12, 'exact_solution':[str(v) for v in q],
            'exact_cost':str(optimal_cost), 'multipliers':[str(v) for v in multipliers],
            'regions':[list(map(float,r)) for r in REGIONS], 'cases':cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='可选：保存数值结果为JSON')
    args = parser.parse_args()
    report = make_report()
    print('最优控制点纵坐标（精确分数）：', ', '.join(report['exact_solution']))
    print('Jerk 平方积分：', report['exact_cost'])
    for key, title in [('initial','初始方案'),('optimized','走廊约束优化方案')]:
        case = report['cases'][key]
        print(f'\n{title}')
        print('  (a,b,c) =', fmt_vector(case['variables']))
        print(f"  J = {case['cost']:.9f}")
        print(f"  全区间速度上界 = {case['speed_bound']:.9f} m/s")
        print(f"  实际速度峰值   = {case['speed_peak']:.9f} m/s")
        print(f"  全区间加速度上界 = {case['acceleration_bound']:.9f} m/s^2")
    print('\n优化后各段局部 Bézier 控制点的 y 坐标：')
    for i, seg in enumerate(report['cases']['optimized']['bezier']):
        print(f'  C{i}:', fmt_vector([point[1] for point in seg]))
    print('\n各段走廊、运动上限、起终状态、C²衔接及独立代价核验全部通过。')
    print('放松问题的最优候选满足全部约束，因此也是正文完整问题的最优解。')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('数值结果已写入：', args.json)

if __name__ == '__main__':
    main()
