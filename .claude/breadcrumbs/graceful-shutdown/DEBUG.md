# Graceful Shutdown — Debug Guide

| Symptom | Check |
|---|---|
| Signal appears ignored | Confirm `handle_shutdown` logged SIGINT/SIGTERM. |
| Shutdown takes several seconds | Manager and Kafka cleanup each have a five-second timeout. |
| Cancellation warning per bin | Expected when active simulator tasks are cancelled and awaited. |
| Process exits after a cleanup warning | Cleanup steps are isolated so later cleanup still runs. |

Inspect `main.handle_shutdown`, `SimulationManager.stop`, `BinSimulator.stop`,
and `KafkaClient.stop`.
