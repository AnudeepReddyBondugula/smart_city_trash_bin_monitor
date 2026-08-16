# Table Creation (Schema Init)

Trigger: `python src/create_tables.py`.
End state: `smart_bins` table exists in Postgres (created if missing, no-op
if already present).

Paths relative to `services/data-simulator/`.

## Flow

```
src/create_tables.py :: entry point   asyncio.run(main())    :23
main()                                                        :16-20
  create_tables()                                             :5-13
    async with engine.begin() as conn:                        :10
      await conn.run_sync(Base.metadata.create_all)           :11
        engine, Base imported from database                   :1
        Base.metadata knows the SmartBin table  src/database.py:13-34
  finally: await engine.dispose()                              :16-20
```

Result: creates all mapped tables **if they don't already exist**
(idempotent); prints confirmation (`:13`).

## Relationship to other flows

Run this **before** `seed.py` — see `../database-seeding/FLOW.md`. Note the
README's Docker quickstart seeds directly (`README.md:38`) — on a fresh
empty DB you generally run `create_tables.py` first, then seed.
