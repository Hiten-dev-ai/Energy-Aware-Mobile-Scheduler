# Energy-Aware Mobile Scheduler

A reproducible Python simulator comparing performance-first, energy-first, and battery-aware scheduling choices for a modeled big.LITTLE processor with DVFS.

## Run

Requires Python 3.10+; no third-party packages are needed.

```powershell
python scheduler.py run --output results
```

The command writes `summary.csv`, `summary.json`, and `comparison.svg` under the selected output directory. Model power and execution rates are illustrative inputs, not measurements from a phone. The simulator does not change a device scheduler.

## Policies

- `performance-first`: chooses the option with shortest estimated execution time.
- `energy-first`: chooses the option with lowest estimated energy.
- `battery-aware`: scores energy and duration against urgency and the remaining modeled battery budget.

## Reproducibility

Workloads and processor parameters are fixed in source. Every policy receives the same workload and battery setting. Results are calculated from the model equations described in the report and README.

## License

MIT. See `LICENSE`.
