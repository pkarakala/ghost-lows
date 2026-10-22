"""Ghost Lows in five minutes: add compression lows to a CGM trace and score the trend alarm.

    pip install git+https://github.com/pkarakala/ghost-lows
    python examples/quickstart.py

What the numbers are not: the trend alarm runs at its default threshold, not the benchmark's
operating point chosen on training patients, so they will not match results/. The sample is
itself simulated with injected faults, and its own artifacts count as real lows here, as on the
benchmark's real-data track.
"""

import ghostlows as gl

# A synthetic 14-day Dexcom Clarity export (5-min CGM, mg/dL); keep the glucose readings
trace = gl.load_clarity(gl.sample_export())
trace = trace[trace["glucose"].notna()]

# One compression artifact (PISA) on every complete night, and no other fault
config = gl.FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"}))
observed, faults = gl.apply_faults(trace, config, seed=1)

# Reference lows come from the trace before the artifacts were added
lows = gl.low_events(trace)
row = gl.score_alarm(gl.TrendAlarm(), observed, lows, faults).iloc[0]

print(f"compression artifacts added: {len(faults)}")
print(f"lows caught (<70 mg/dL): {row['caught_l1']:.0f} of {row['events_l1']:.0f}")
print(
    f"false alarms per day: {row['false_per_day']:.2f} "
    f"({row['false_compression_per_day']:.2f} from compression)"
)
print(f"median warning before a caught low: {row['warning_median_min_l1']:.0f} min")
