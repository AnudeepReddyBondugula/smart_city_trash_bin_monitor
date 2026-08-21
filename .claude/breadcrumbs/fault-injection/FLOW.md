# Fault Injection

Trigger: `SimulationManager.initialize()`, once at simulator startup.

```text
load ACTIVE bins from smart_bins
  → build every Bin
  → assign_fault_modes(bins)          # int(len * FAULT_INJECTION_RATE) bins
       index 0,1,2,... cycle through FAULT_MODES
  → start one BinSimulator per bin
  → each tick: _simulate() applies state-level faults
               _next_payload() applies reporting-level faults
```

Faults exist so the detectors downstream have something to detect. Without them
the offline, stuck-sensor, duplicate, sensor-fault, fire-risk and SLA rules can
be written but never once observed working.

| Mode | Applied in | Proves |
|---|---|---|
| `SILENT` | `_next_payload` | `OFFLINE` |
| `FROZEN` | `_simulate` | `SENSOR_STUCK` |
| `SPIKE` | `_next_payload` (`_corrupt`) | `SENSOR_FAULT` and the dead-letter path |
| `DUPLICATE` | `_next_payload` | deduplication |
| `HOT` | `_simulate_temperature` | `FIRE_RISK` |
| `JUMP` | `_simulate_fill` | `ANOMALY_JUMP` |
| `UNCOLLECTED` | `_simulate_fill` | `SLA_BREACH` |

Assignment cycles rather than drawing per bin. Independent draws can leave a
small fleet with no `HOT` bin at all, so no fire alert appears anywhere in the
run — indistinguishable from a broken detector.

Set `FAULT_INJECTION_RATE=0` for a fleet where nothing ever goes wrong.
