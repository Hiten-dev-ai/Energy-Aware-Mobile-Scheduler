#!/usr/bin/env python3
"""Deterministic big.LITTLE + DVFS scheduling simulator; estimates only."""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Option:
    core: str
    frequency: str
    rate: float       # workload units per second
    power: float      # modeled watts
    slots: int


@dataclass
class Task:
    task_id: str
    arrival_s: float
    work: float       # normalized work units
    urgency: int      # 1=background, 5=interactive/critical
    deadline_s: float | None


OPTIONS = (
    Option("LITTLE", "low", 40, 0.55, 4),
    Option("LITTLE", "mid", 60, 0.85, 4),
    Option("LITTLE", "high", 80, 1.30, 4),
    Option("big", "low", 75, 1.25, 2),
    Option("big", "mid", 115, 2.10, 2),
    Option("big", "high", 155, 3.40, 2),
)


def workloads() -> dict[str, list[Task]]:
    return {
        "A-mixed": [
            Task("A1", 0.000, 1.5, 5, .045), Task("A2", .006, 5.0, 2, .180),
            Task("A3", .012, 2.4, 4, .095), Task("A4", .020, 7.0, 1, .400),
            Task("A5", .024, 1.2, 5, .070), Task("A6", .032, 4.0, 3, .190),
            Task("A7", .043, 3.0, 2, .230), Task("A8", .050, 1.8, 4, .140),
        ],
        "B-low-battery": [
            Task("B1", 0, 2.0, 3, .100), Task("B2", .008, 6.0, 1, .300),
            Task("B3", .016, 1.5, 4, .100), Task("B4", .022, 5.0, 2, .280),
            Task("B5", .034, 2.2, 3, .170), Task("B6", .041, 3.5, 1, .300),
        ],
        "C-urgent": [
            Task("C1", 0, 1.3, 5, .030), Task("C2", .004, 1.8, 5, .040),
            Task("C3", .009, 2.0, 4, .055), Task("C4", .015, 6.0, 1, .300),
            Task("C5", .021, 1.2, 5, .060), Task("C6", .030, 4.5, 2, .220),
            Task("C7", .036, 1.4, 4, .085),
        ],
        "D-background": [
            Task(f"D{i}", i * .010, 2.0 + (i % 3), 1, .500 + i * .010)
            for i in range(1, 11)
        ],
    }


def battery_weight(percent: float) -> float:
    if percent <= 20:
        return 1.8
    if percent <= 50:
        return 1.0
    return 0.35


def choose(policy: str, task: Task, battery_percent: float) -> Option:
    if policy == "performance-first":
        return min(OPTIONS, key=lambda o: task.work / o.rate)
    if policy == "energy-first":
        return min(OPTIONS, key=lambda o: o.power * task.work / o.rate)
    # Scale both terms to useful ranges, then give urgent tasks more weight.
    urgent = (task.urgency - 1) / 4
    b_weight = battery_weight(battery_percent)
    def score(o: Option) -> tuple[float, float, str, str]:
        duration = task.work / o.rate
        energy = o.power * duration
        latency_cost = duration * (0.35 + 1.35 * urgent)
        energy_cost = energy * b_weight
        deadline_cost = 0.0
        if task.deadline_s is not None and duration > task.deadline_s:
            deadline_cost = (duration - task.deadline_s) * (2.0 + 2.0 * urgent)
        return (energy_cost + latency_cost + deadline_cost, duration, o.core, o.frequency)
    return min(OPTIONS, key=score)


def simulate(policy: str, tasks: Iterable[Task], battery_percent: float) -> dict:
    ordered = sorted(tasks, key=lambda t: (t.arrival_s, -t.urgency, t.task_id))
    # Frequency options on a core class share the same physical core slots.
    availability = {"LITTLE": [0.0] * 4, "big": [0.0] * 2}
    rows = []
    total_energy = 0.0
    remaining_battery = battery_percent
    battery_budget_j = 400.0 * battery_percent / 100.0
    for task in ordered:
        current = choose(policy, task, remaining_battery)
        slots = availability[current.core]
        slot_i = min(range(len(slots)), key=slots.__getitem__)
        start = max(task.arrival_s, slots[slot_i])
        duration = task.work / current.rate
        finish = start + duration
        energy = current.power * duration
        slots[slot_i] = finish
        total_energy += energy
        remaining_battery = max(0.0, 100.0 * (battery_budget_j - total_energy) / 400.0)
        rows.append({
            "task": task.task_id, "arrival_s": task.arrival_s, "start_s": start,
            "finish_s": finish, "response_s": start - task.arrival_s,
            "turnaround_s": finish - task.arrival_s, "core": current.core,
            "frequency": current.frequency, "duration_s": duration,
            "energy_j": energy, "deadline_miss": bool(task.deadline_s and finish > task.deadline_s),
        })
    n = len(rows)
    avg = lambda k: sum(row[k] for row in rows) / n if n else 0.0
    return {
        "policy": policy, "tasks": n, "avg_response_ms": avg("response_s") * 1000,
        "avg_turnaround_ms": avg("turnaround_s") * 1000,
        "completion_time_ms": max((r["finish_s"] for r in rows), default=0) * 1000,
        "estimated_energy_j": total_energy, "deadline_misses": sum(r["deadline_miss"] for r in rows),
        "initial_battery_percent": battery_percent,
        "final_battery_percent": remaining_battery, "task_details": rows,
    }


def run_all() -> list[dict]:
    rows = []
    policy_names = ("performance-first", "energy-first", "battery-aware")
    cases = [(name, ts, 80 if name != "B-low-battery" else 20) for name, ts in workloads().items()]
    for case, tasks, battery in cases:
        for policy in policy_names:
            result = simulate(policy, tasks, battery)
            result["workload"] = case
            rows.append(result)
    for battery in (80, 50, 20):
        for policy in policy_names:
            result = simulate(policy, workloads()["A-mixed"], battery)
            result["workload"] = f"E-battery-sweep-{battery}%"
            rows.append(result)
    return rows


def write_svg(rows: list[dict], path: Path) -> None:
    chosen = [r for r in rows if r["workload"] == "A-mixed"]
    colors = {"performance-first": "#1d4ed8", "energy-first": "#16a34a", "battery-aware": "#c2410c"}
    max_energy = max(r["estimated_energy_j"] for r in chosen) * 1.2
    bars = []
    for i, row in enumerate(chosen):
        y = 70 + i * 76
        width = 380 * row["estimated_energy_j"] / max_energy
        bars.append(f'<text x="18" y="{y+18}" font-size="15">{row["policy"]}</text>'
                    f'<rect x="190" y="{y}" width="{width:.1f}" height="28" rx="5" fill="{colors[row["policy"]]}"/>'
                    f'<text x="{198+width:.1f}" y="{y+19}" font-size="13">{row["estimated_energy_j"]:.3f} J</text>'
                    f'<text x="190" y="{y+48}" font-size="12" fill="#475569">Avg response {row["avg_response_ms"]:.2f} ms</text>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="820" height="320" viewBox="0 0 820 320">'
           '<rect width="100%" height="100%" fill="#fff"/><text x="18" y="32" font-size="19" font-weight="700">Workload A: energy and response trade-off</text>'
           '<text x="190" y="55" font-size="12" fill="#475569">Estimated energy (J); fixed workload, 80% initial battery</text>'
           + ''.join(bars) + '<text x="18" y="300" font-size="11" fill="#64748b">Model estimates only; not measured hardware consumption.</text></svg>')
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run fixed workloads and write result files")
    run.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    rows = run_all()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = [{k: v for k, v in row.items() if k != "task_details"} for row in rows]
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fields = list(summary[0])
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    (args.output / "task_timelines.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_svg(rows, args.output / "comparison.svg")
    print("ENERGY-AWARE BIG.LITTLE SCHEDULER — MODEL RUN")
    print("Illustrative estimates only; no phone hardware was measured.\n")
    print(f"{'Workload':<24} {'Policy':<18} {'Resp ms':>8} {'TAT ms':>8} {'Energy J':>9} {'Miss':>5}")
    for row in rows:
        if row["workload"] in {"A-mixed", "B-low-battery", "C-urgent", "D-background"}:
            print(f"{row['workload']:<24} {row['policy']:<18} {row['avg_response_ms']:>8.2f} "
                  f"{row['avg_turnaround_ms']:>8.2f} {row['estimated_energy_j']:>9.3f} {row['deadline_misses']:>5}")
    print(f"\nWrote {len(rows)} policy runs to {args.output.resolve()}")


if __name__ == "__main__":
    main()
