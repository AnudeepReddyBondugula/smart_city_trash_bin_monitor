# Database Seeding

Trigger: `python src/seed.py --count 50 [--clear]` (Docker form in
`README.md:38`: `docker compose run --rm data_simulator python src/seed.py --count 50`).
End state: `count` mock `SmartBin` rows committed to `smart_bins`, status `ACTIVE`.

Paths relative to `services/data-simulator/`.

## Flow

```
src/seed.py :: entry point (arg parsing)         :51-59
  --count (default 50)                            :53-55
  --clear (flag)                                  :56-58
  asyncio.run(seed_db(args.count, args.clear))     :61

seed_db()
  safety guard: count > 500 → return early         :16-18
  connect: own engine + session factory            :21-22
    from settings.DATABASE_URL (get_settings() :11)
  if --clear: delete(SmartBin) + commit             :26-29
  generate rows (loop count times)                  :31-42
    bin_id = f"BIN-{uuid4().hex[:8].upper()}-X"      :33
    capacity = 100.0                                 :36
    latitude/longitude via Faker                     :37-38
    status = "ACTIVE"                                :39
    session.add(...)                                 :41
  commit (one commit for all rows)                   :43-44
  finally: engine.dispose()                          :47-48
```

## Downstream effect

Seeded `ACTIVE` bins are what `SimulationManager.initialize()` loads on the
next simulator start (`src/simulator/simulation_manager.py:44`). Per
`README.md:31`, the simulator emits nothing until the DB is seeded — see
`../startup-and-telemetry/FLOW.md`.
