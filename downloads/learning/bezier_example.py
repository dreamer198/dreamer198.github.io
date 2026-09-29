"""复算《Bézier 曲线：一步一步用控制点生成和检查轨迹》。

仅使用 Python 标准库；运行：python bezier_example.py
坐标单位为米，时间单位为秒。矩形禁行区已计入机体尺寸。
"""
from __future__ import annotations

from math import comb, hypot, isclose, isfinite
from typing import Sequence

Point = tuple[float, float]
CONTROL_POINTS: tuple[Point, ...] = ((0., 0.), (2., 4.), (6., 4.), (8., 0.))
MOVED_POINTS: tuple[Point, ...] = ((0., 0.), (2., 1.5), (6., 4.), (8., 0.))


def checked_points(points: Sequence[Point]) -> list[Point]:
    if not points:
        raise ValueError("至少需要一个控制点。")
    result = []
    for p in points:
        if len(p) != 2 or not all(isfinite(float(x)) for x in p):
            raise ValueError("控制点必须包含两个有限坐标。")
        result.append((float(p[0]), float(p[1])))
    return result


def lerp(a: Point, b: Point, s: float) -> Point:
    return ((1. - s) * a[0] + s * b[0], (1. - s) * a[1] + s * b[1])


def casteljau_levels(points: Sequence[Point], s: float) -> list[list[Point]]:
    """返回逐层插值的所有中间点；最后一层只有曲线点。"""
    if not isfinite(s) or not 0. <= s <= 1.:
        raise ValueError("参数 s 必须处于 [0, 1]。")
    levels = [checked_points(points)]
    while len(levels[-1]) > 1:
        row = levels[-1]
        levels.append([lerp(a, b, s) for a, b in zip(row, row[1:])])
    return levels


def evaluate(points: Sequence[Point], s: float) -> Point:
    return casteljau_levels(points, s)[-1][0]


def bernstein_evaluate(points: Sequence[Point], s: float) -> Point:
    pts = checked_points(points)
    if not isfinite(s) or not 0. <= s <= 1.:
        raise ValueError("参数 s 必须处于 [0, 1]。")
    degree = len(pts) - 1
    weights = [comb(degree, i) * (1. - s)**(degree - i) * s**i
               for i in range(degree + 1)]
    return tuple(sum(w * p[d] for w, p in zip(weights, pts))
                 for d in range(2))


def derivative_controls(points: Sequence[Point], duration: float,
                        order: int = 1) -> list[Point]:
    """s=t/T 时，对实际时间求 order 次导数的控制向量。"""
    if not isfinite(duration) or duration <= 0.:
        raise ValueError("本段持续时间必须为有限正数。")
    if not isinstance(order, int) or isinstance(order, bool) or order < 0:
        raise ValueError("导数阶数必须为非负整数。")
    result = checked_points(points)
    for _ in range(order):
        n = len(result) - 1
        if n == 0:
            return [(0., 0.)]
        factor = n / duration
        result = [(factor * (b[0] - a[0]), factor * (b[1] - a[1]))
                  for a, b in zip(result, result[1:])]
    return result


def state(points: Sequence[Point], time: float, duration: float,
          order: int = 0) -> Point:
    controls = derivative_controls(points, duration, order)
    return evaluate(controls, time / duration)


def split(points: Sequence[Point], s: float) -> tuple[list[Point], list[Point]]:
    levels = casteljau_levels(points, s)
    return [row[0] for row in levels], [row[-1] for row in reversed(levels)]


def magnitude_bound(points: Sequence[Point], duration: float,
                    order: int) -> float:
    return max(hypot(*p) for p in derivative_controls(points, duration, order))


def in_obstacle(point: Point) -> bool:
    x, y = point
    return 3. <= x <= 5. and 0. <= y <= 2.


def in_left_region(point: Point, tol: float = 1e-12) -> bool:
    x, y = point
    return -tol <= x <= 4. + tol and .75 * x - tol <= y <= 4. + tol


def in_right_region(point: Point, tol: float = 1e-12) -> bool:
    x, y = point
    return 4. - tol <= x <= 8. + tol and .75 * (8. - x) - tol <= y <= 4. + tol


def check_close(actual: Point, expected: Point, label: str) -> None:
    if not all(isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
               for a, b in zip(actual, expected)):
        raise AssertionError(f"{label}: 实际 {actual}，预期 {expected}")


def main() -> None:
    P = CONTROL_POINTS
    print("一、两种曲线计算方法")
    expected = {0.: (0., 0.), .25: (1.8125, 2.25), .5: (4., 3.),
                .75: (6.1875, 2.25), 1.: (8., 0.)}
    for s, point in expected.items():
        check_close(evaluate(P, s), point, "示例曲线点")
        print(f"s={s:.2f}: {evaluate(P, s)}")
    for i in range(101):
        check_close(evaluate(P, i / 100), bernstein_evaluate(P, i / 100),
                    "插值与 Bernstein 表示")

    print("\n二、移动控制点")
    moved = evaluate(MOVED_POINTS, .4)
    check_close(moved, (3.104, 1.8), "移动后的碰撞点")
    if not in_obstacle(moved):
        raise AssertionError("预期的新曲线碰撞点未进入矩形。")
    if any(in_obstacle(p) for p in MOVED_POINTS):
        raise AssertionError("预期所有控制点本身位于禁行区外。")
    print(f"s=0.4: {moved}，该点在禁行区域内")

    print("\n三、速度与加速度的全区间上界")
    for T in (4., 8.):
        vmax = magnitude_bound(P, T, 1)
        amax = magnitude_bound(P, T, 2)
        print(f"T={T:g} 秒: 速度界={vmax:.8f}, 加速度界={amax:.8f}")
        # 此算例的上界在端点取得，因此同时也是实际最大值。
        if not isclose(hypot(*state(P, 0., T, 1)), vmax):
            raise AssertionError("速度上界未在起点达到。")
        if not isclose(hypot(*state(P, 0., T, 2)), amax):
            raise AssertionError("加速度上界未在起点达到。")
    if magnitude_bound(P, 8., 1) > 2. or magnitude_bound(P, 8., 2) > 1.:
        raise AssertionError("8 秒方案未满足给定运动上限。")
    check_close(state(P, 4., 8., 1), (1.125, 0.), "第 4 秒速度")
    check_close(state(P, 4., 8., 2), (0., -.375), "第 4 秒加速度")

    print("\n四、曲线分割与凸区域包含")
    left, right = split(P, .5)
    print("左控制点:", left)
    print("右控制点:", right)
    if not all(in_left_region(p) for p in left):
        raise AssertionError("左控制点不满足左侧凸区域约束。")
    if not all(in_right_region(p) for p in right):
        raise AssertionError("右控制点不满足右侧凸区域约束。")
    # 下列采样仅用于复核代码中的分割实现。
    # 连续时间安全的依据是正文证明的凸区域包含与区域、障碍的分离。
    for i in range(101):
        u = i / 100
        check_close(evaluate(left, u), evaluate(P, u / 2), "左半段分割")
        check_close(evaluate(right, u), evaluate(P, (1. + u) / 2), "右半段分割")
    print("两组控制点分别满足对应区域的全部线性不等式。")
    print("与障碍横向范围重叠时，两个区域均有 y >= 2.25 > 2。")

    print("\n五、连接处的状态")
    for order, name in [(0, "位置"), (1, "速度"), (2, "加速度")]:
        L = state(left, 4., 4., order)
        R = state(right, 0., 4., order)
        check_close(L, R, name + "衔接")
        check_close(L, state(P, 4., 8., order), name + "与原曲线一致")
        print(f"{name}: 左 {L}；右 {R}")
    print("\n全部验证通过。")


if __name__ == "__main__":
    main()
