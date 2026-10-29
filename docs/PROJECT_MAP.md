# Project Map

## Purpose

Deterministic, standard-library simulator for comparing three scheduling policies across a modeled two-class big.LITTLE processor with DVFS. Every power, throughput and battery value is illustrative; no hardware scheduler is changed.

## Behavior lookup

| Behavior | Owner | Inputs and outputs | Verification |
|---|---|---|---|
| Define processor options and fixed task sets | `scheduler.py`: `OPTIONS`, `workloads()` | Core/frequency rates and power; task arrival, work, urgency, deadline | Run CLI and inspect JSON/CSV |
| Select an option | `scheduler.py`: `choose()` | Policy, task, current modeled battery percentage -> core/frequency option | Compare same workload across policies |
| Simulate allocation and calculate metrics | `scheduler.py`: `simulate()` | Task set and initial battery -> per-task timeline and run metrics | Check timeline and summary output |
| Run all report cases and export artifacts | `scheduler.py`: `run_all()`, `main()` | Fixed cases -> JSON, CSV, timeline JSON, SVG chart, terminal summary | `python scheduler.py run --output results` |

## Files

- `scheduler.py`: full executable CLI and model.
- `README.md`: setup, usage, policy definitions, and limitations.
- `LICENSE`: MIT license.
- `.gitignore`: excludes generated runtime outputs and Python caches.

## Flow and constraints

`main()` calls `run_all()`, which passes each fixed task set to `simulate()` under each policy. `simulate()` calls `choose()` once per task, selects an available slot for the chosen core/frequency, updates modeled energy/battery, and derives response, turnaround, finish, and deadline metrics. `main()` serializes those results and renders an SVG from the same summary rows. The model assumes fixed rates/power and omits thermal, memory, OS, radio, and display energy.

## Coverage

All first-party files listed above are mapped. No third-party runtime dependencies or hardware integration exist. Checked after implementation: source, README, license, ignore rules, and this map. Runtime verification is the CLI run that produces the report artifacts.
