#!/usr/bin/env python3
"""复算《B 样条轨迹优化：一步一步计算控制点的移动》。

仅使用 Python 标准库。
    python bspline_optimization_example.py
    python bspline_optimization_example.py --json result.json

本例使用固定三次均匀 B 样条、每段 2 秒、一个侧向变量 q。
几何包络、目标函数和可行区间均与博客正文一致。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

Point = tuple[float, float]
H = 2.0
D_REF = 2.25
Q_MIN, Q_MAX = 3.0, 5.0
Q_OPT = 717.0 / 154.0
BASIS = (
    (1/6, -1/2, 1/2, -1/6),
    (2/3, 0, -1, 1/2),
    (1/6, 1/2, 1/2, -1/2),
    (0, 0, 0, 1/6),
)


def controls(q: float) -> list[Point]:
    if not math.isfinite(q):
        raise ValueError("q 必须是有限数。")
    ys = [0.0, 0.0, 0.0, 3.0, q, 3.0, 0.0, 0.0, 0.0]
    return [(2.0 * i - 2.0, y) for i, y in enumerate(ys)]


def poly_value(coefficients, x: float, derivative: int = 0) -> float:
    if derivative < 0:
        raise ValueError("导数阶数必须非负。")
    values = list(coefficients)
    for _ in range(derivative):
        values = [i * values[i] for i in range(1, len(values))]
    result = 0.0
    for c in reversed(values):
        result = result * x + c
    return result


def span(q: float, i: int, s: float, derivative: int = 0) -> Point:
    if not 0 <= i < 6 or not 0 <= s <= 1:
        raise ValueError("段编号应为 0～5，局部参数应在 [0,1] 内。")
    ps = controls(q)[i:i+4]
    ws = [poly_value(b, s, derivative) / H**derivative for b in BASIS]
    return tuple(sum(w * p[k] for w, p in zip(ws, ps)) for k in (0, 1))


def curve(q: float, t: float, derivative: int = 0) -> Point:
    if not math.isfinite(t) or not 0 <= t <= 12:
        raise ValueError("总时间必须在 [0,12] 秒内。")
    i = min(int(t / H), 5)
    return span(q, i, t / H - i, derivative)


def third_differences(q: float) -> list[Point]:
    ps = controls(q)
    return [tuple(ps[i+3][k] - 3*ps[i+2][k] + 3*ps[i+1][k] - ps[i][k]
                  for k in (0, 1)) for i in range(6)]


def cost_terms(q: float) -> dict[str, float]:
    """数值上使用正文的单位归一化，返回无量纲代价。"""
    if q < Q_MIN:
        raise ValueError("本例距离表达式按 q >= 3 的上方通行分支使用。")
    # 每段的 Jerk 恒定，以下积分是解析计算，而非时间采样近似。
    smoothness = sum(x*x + y*y for x, y in third_differences(q)) / H**5
    midpoint = curve(q, 6.0)
    gap = midpoint[1] - 2.0
    deficit = max(0.0, D_REF - gap)
    distance_cost = deficit**2
    return {"smoothness": smoothness, "distance_cost": distance_cost,
            "cost": smoothness + distance_cost,
            "gap": gap, "middle_y": midpoint[1]}


def gradient(q: float) -> float:
    terms = cost_terms(q)
    deficit = max(0.0, D_REF - terms["gap"])
    return 1.25*q - 45.0/8.0 - (4.0/3.0)*deficit


def bezier_controls(q: float, i: int) -> list[Point]:
    p = controls(q)[i:i+4]
    weights = ((1/6, 4/6, 1/6, 0), (0, 2/3, 1/3, 0),
               (0, 1/3, 2/3, 0), (0, 1/6, 4/6, 1/6))
    return [tuple(sum(w*p[j][k] for j, w in enumerate(ws)) for k in (0, 1))
            for ws in weights]


def bounds(q: float) -> tuple[float, float]:
    ps = controls(q)
    speed = max(math.hypot(ps[i+1][0] - ps[i][0], ps[i+1][1] - ps[i][1]) / H
                for i in range(8))
    acc = max(math.hypot(*(ps[i][k] - 2*ps[i+1][k] + ps[i+2][k] for k in (0, 1))) / H**2
              for i in range(7))
    return speed, acc


def feasible(q: float) -> bool:
    """用导数凸组合和局部 Bézier 凸包检查整段约束。"""
    if not math.isfinite(q) or not Q_MIN <= q <= Q_MAX:
        return False
    speed, acc = bounds(q)
    if speed > 2.0 + 1e-12 or acc > 1.0 + 1e-12:
        return False
    for i in range(6):
        for x, y in bezier_controls(q, i):
            if not (-3 <= x <= 15 and -1 <= y <= 6):
                return False
            if i in (2, 3) and not (4-1e-12 <= x <= 8+1e-12 and 2.5-1e-12 <= y <= 4.5+1e-12):
                return False
    # 其余段的 x 区间分别为 [0,2]、[2,4]、[8,10]、[10,12]。
    # 中间两段位于 F=[4,8]×[2.5,4.5]；禁行区顶端为 y=2。
    return True


def motion_extrema(q: float) -> dict[str, float]:
    """本例 vx 恒为 1，vy 为二次式、ay 为一次式，可逐段检查极值。"""
    speed_max, speed_t = 0.0, 0.0
    acc_max, acc_t = 0.0, 0.0
    for i in range(6):
        candidates = [0.0, 1.0]
        ay0, ay1 = span(q, i, 0, 2)[1], span(q, i, 1, 2)[1]
        if abs(ay1 - ay0) > 1e-14:
            root = -ay0 / (ay1 - ay0)
            if 0 < root < 1:
                candidates.append(root)
        for s in candidates:
            value = math.hypot(*span(q, i, s, 1))
            if value > speed_max:
                speed_max, speed_t = value, H*(i+s)
        for s in (0.0, 1.0):
            value = math.hypot(*span(q, i, s, 2))
            if value > acc_max:
                acc_max, acc_t = value, H*(i+s)
    return {"speed_max": speed_max, "speed_time": speed_t,
            "acc_max": acc_max, "acc_time": acc_t}


def optimize(initial_step: float = 0.2, max_iterations: int = 80) -> list[dict]:
    if initial_step <= 0 or not math.isfinite(initial_step):
        raise ValueError("更新系数必须为正的有限数。")
    q = 3.0
    history = []
    for k in range(max_iterations + 1):
        terms, g = cost_terms(q), gradient(q)
        history.append({"iteration": k, "q": q, "gradient": g, **terms})
        if abs(g) < 1e-7 or k == max_iterations:
            break
        step = initial_step
        for _ in range(50):
            trial = q - step*g
            if feasible(trial) and cost_terms(trial)["cost"] <= terms["cost"] - 1e-4*step*g*g + 1e-14:
                break
            step *= 0.5
        else:
            raise RuntimeError("未能找到通过检查且降低代价的更新。")
        history[-1]["accepted_step"] = step
        q = trial
    return history


def assert_close(a: float, b: float, tol: float = 1e-9) -> None:
    if not math.isclose(a, b, rel_tol=tol, abs_tol=tol):
        raise AssertionError(f"数值不一致：{a} 与 {b}")


def verify() -> None:
    for q in (3.0, 3.5, 4.5, Q_OPT, 4.875, 5.0):
        assert feasible(q)
        assert_close(cost_terms(q)["smoothness"], (5*q*q - 45*q + 117)/8)
        assert_close(curve(q, 6)[1], 1 + 2*q/3)
        # 直接对每段多项式求三次导数，独立核对 Jerk 和积分。
        direct_cost = 0.0
        for i, (dx, dy) in enumerate(third_differences(q)):
            j = span(q, i, 0.37, 3)
            assert_close(j[0], dx/H**3)
            assert_close(j[1], dy/H**3)
            direct_cost += H*sum(value*value for value in j)
        assert_close(direct_cost, cost_terms(q)["smoothness"])
        # 验证五个内节点的 C2 连续性。
        for i in range(5):
            for order in range(3):
                left, right = span(q, i, 1, order), span(q, i+1, 0, order)
                for a, b in zip(left, right):
                    assert_close(a, b)
        for time, expected in ((0, (0, 0)), (12, (12, 0))):
            for a, b in zip(curve(q, time), expected):
                assert_close(a, b)
            for a, b in zip(curve(q, time, 1), (1, 0)):
                assert_close(a, b)
            for a in curve(q, time, 2):
                assert_close(a, 0)
    # 有限差分独立核对解析梯度，包含罚项激活和不激活的两侧。
    for q in (3.2, 4.0, 4.8, 4.95):
        e = 1e-5
        numeric = (cost_terms(q+e)["cost"]-cost_terms(q-e)["cost"])/(2*e)
        assert_close(numeric, gradient(q), 1e-7)
    assert_close(gradient(Q_OPT), 0)
    assert_close(cost_terms(Q_OPT)["cost"], 4941/2464)
    assert not feasible(3.0-gradient(3.0))
    history = optimize()
    assert_close(history[-1]["q"], Q_OPT, 1e-7)
    assert all(b["cost"] <= a["cost"]+1e-12 for a, b in zip(history, history[1:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="可选：将复算结果保存为 JSON")
    args = parser.parse_args()
    verify()
    history = optimize()
    print("全部核验通过：导数、梯度、衔接、凸区域和运动上限。")
    print("轮次       q           平滑项        间距项        总代价        梯度")
    for row in history[:13]:
        print(f'{row["iteration"]:2d}  {row["q"]:11.7f}  {row["smoothness"]:11.7f}  '
              f'{row["distance_cost"]:11.7f}  {row["cost"]:11.7f}  {row["gradient"]:11.7f}')
    final = history[-1]
    print(f'迭代终点 q = {final["q"]:.9f}；解析最低点 717/154 = {Q_OPT:.9f}')
    print(f'中点额外间距 = {final["gap"]:.9f} m；总分 = {final["cost"]:.9f}')
    print("速度、加速度上界：", bounds(Q_OPT))
    print("实际运动极值：", motion_extrema(Q_OPT))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {"history": history, "q_opt": Q_OPT, "optimal": cost_terms(Q_OPT),
                   "baseline": cost_terms(3.0), "bounds": bounds(Q_OPT),
                   "extrema": motion_extrema(Q_OPT)}
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
