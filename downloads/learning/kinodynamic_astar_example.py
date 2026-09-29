"""复算《Kinodynamic A*：一步一步把速度放进搜索》的 4 米算例。

运行：python kinodynamic_astar_example.py
仅使用 Python 标准库。状态以半米位置索引和整数速度精确存储。
设置：一维静态通道，0 <= p <= 4，0 <= v <= 2，u in {1,0,-1}，dt=1。
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import heapq
from itertools import count
import json
from pathlib import Path
import sys


@dataclass(frozen=True)
class State:
    p2: int  # 位置的两倍；例如 p2=3 表示 1.5 米。
    v: int   # 速度，米/秒。

    @property
    def p(self) -> Fraction:
        return Fraction(self.p2, 2)

    def label(self) -> str:
        return f'({float(self.p):g}, {self.v})'


START = State(0, 0)
GOAL = State(8, 0)
CONTROLS = (1, 0, -1)  # 相同优先级时，新状态的插入顺序由这里确定。


def state_valid(s: State) -> bool:
    return 0 <= s.p2 <= 8 and 0 <= s.v <= 2


def propagate(s: State, u: int) -> tuple[State, str | None]:
    if u not in CONTROLS:
        raise ValueError('本例只允许加速度 +1、0、-1。')
    target = State(s.p2 + 2 * s.v + u, s.v + u)
    # 一秒内速度线性变化；首尾速度在 [0,2]，全段速度就满足此约束。
    if not 0 <= target.v <= 2:
        return target, '速度越界'
    # 合格速度始终非负，位置单调，因此一维位置区间可由端点检查。
    if not 0 <= target.p2 <= 8:
        return target, '位置越界'
    return target, None


def heuristic(s: State) -> Fraction:
    distance_time = Fraction(8 - s.p2, 4)  # (4-p) / 2
    stop_time = Fraction(s.v)             # v / 1
    return max(distance_time, stop_time)


def search(use_heuristic: bool = True) -> dict:
    if not state_valid(START) or not state_valid(GOAL):
        raise ValueError('起终状态越界。')
    estimate = heuristic if use_heuristic else (lambda _s: Fraction(0))
    serial = count()
    best: dict[State, int] = {START: 0}
    parent: dict[State, tuple[State, int]] = {}
    queue = []
    heapq.heappush(queue, (estimate(START), estimate(START), next(serial), 0, START))
    trace = []
    expanded = set()
    while queue:
        f, h, order, saved_g, s = heapq.heappop(queue)
        if saved_g != best.get(s):
            continue  # 先排除已过期记录，再判断目标。
        row = {'state': s.label(), 'p': float(s.p), 'v': s.v,
               'g': saved_g, 'h': float(h), 'f': float(f), 'edges': []}
        trace.append(row)
        if s == GOAL:
            path = [s]
            controls = []
            while path[-1] != START:
                previous, u = parent[path[-1]]
                controls.append(u)
                path.append(previous)
            path.reverse()
            controls.reverse()
            return {
                'cost': saved_g,
                'path': [{'p': float(x.p), 'v': x.v} for x in path],
                'controls': controls,
                'trace': trace,
                'discovered': [{'p': float(x.p), 'v': x.v} for x in best],
                'expanded_count': len(expanded),
            }
        expanded.add(s)
        for u in CONTROLS:
            target, reason = propagate(s, u)
            edge = {'u': u, 'target': target.label(), 'reason': reason}
            row['edges'].append(edge)
            if reason:
                continue
            new_g = saved_g + 1
            old_g = best.get(target)
            edge.update(new_g=new_g, old_g=old_g)
            if old_g is not None and new_g >= old_g:
                edge['reason'] = '保留已有较优或等价记录'
                continue
            best[target] = new_g
            parent[target] = (s, u)
            ht = estimate(target)
            heapq.heappush(queue, (new_g + ht, ht, next(serial), new_g, target))
            edge.update(reason='新增' if old_g is None else '更新',
                        h=float(ht), f=float(new_g + ht))
    raise RuntimeError('本例离散运动图中没有找到目标状态。')


def self_check(result: dict) -> None:
    assert result['cost'] == 4
    assert result['controls'] == [1, 1, -1, -1]
    assert result['path'] == [
        {'p': 0.0, 'v': 0}, {'p': 0.5, 'v': 1}, {'p': 2.0, 'v': 2},
        {'p': 3.5, 'v': 1}, {'p': 4.0, 'v': 0}]
    expected_order = ['(0, 0)', '(0.5, 1)', '(1.5, 1)', '(1, 0)',
                      '(2.5, 1)', '(2, 0)', '(2, 2)', '(3.5, 1)', '(4, 0)']
    assert [row['state'] for row in result['trace']] == expected_order
    assert search(False)['cost'] == result['cost']  # 与 Dijkstra 对照。
    assert heuristic(GOAL) == 0
    # 穷举这个有限格点状态集上的可行边，验证启发函数的一致性。
    for p2 in range(9):
        for v in range(3):
            s = State(p2, v)
            for u in CONTROLS:
                target, reason = propagate(s, u)
                if reason is None:
                    assert heuristic(s) <= 1 + heuristic(target)
    # 回放输出运动；这里的精确全段约束由 propagate 中的单调性证明保证。
    state = START
    for u in result['controls']:
        state, reason = propagate(state, u)
        assert reason is None
    assert state == GOAL
    # 二维例子：实际曲线中点碰撞，连接端点的直线在障碍上方。
    tau = Fraction(1, 2)
    x = 2 + tau
    y = 2 + tau * tau / 2
    assert Fraction(24,10) <= x <= Fraction(26,10)
    assert Fraction(205,100) <= y <= Fraction(218,100)
    assert 2 + Fraction(1,2) * Fraction(4,10) > Fraction(218,100)


def main() -> None:
    result = search()
    self_check(result)
    print('轮次 | 取出状态 (位置,速度) | g | h | f')
    for n, row in enumerate(result['trace'], 1):
        print(f"{n:>4} | {row['state']:>16} | {row['g']:g} | {row['h']:g} | {row['f']:g}")
        for e in row['edges']:
            print(f"     u={e['u']:+d} -> {e['target']}：{e['reason']}")
    print('\n最终状态序列：')
    print(' → '.join(f"({s['p']:g}, {s['v']:g})" for s in result['path']))
    print('每秒的加速度：', result['controls'])
    print('总时间：', result['cost'], '秒')
    print('自检通过：状态传播、搜索顺序、启发函数和最短时间均已核对。')
    if len(sys.argv) == 3 and sys.argv[1] == '--json':
        output = Path(sys.argv[2])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    elif len(sys.argv) != 1:
        raise SystemExit('用法：python kinodynamic_astar_example.py [--json 输出文件路径]')


if __name__ == '__main__':
    main()
