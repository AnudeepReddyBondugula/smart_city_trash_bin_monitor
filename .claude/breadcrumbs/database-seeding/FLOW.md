# Database Seeding

Trigger: `python src/seed.py --count 50 [--clear]` after migrations are current.

```text
argparse reads --count and --clear
  → reject count > 500
  → create an async engine from settings.DATABASE_URL
  → optionally DELETE all SmartBin rows and commit
  → for each new row:
      generate BIN-<8 hex>-X
      select CENTRAL/NORTH/SOUTH/EAST/WEST
      generate coordinates in that Hyderabad zone
      set capacity=100, status=ACTIVE
  → commit all new rows
  → dispose the engine
```

The simulator loads active rows only at startup. After seeding, recreate or
restart the running process so `SimulationManager.initialize()` reloads them.
