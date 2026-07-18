import asyncio
import argparse

from database import SmartBin
from config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from faker import Faker
from sqlalchemy import delete
import uuid

fake = Faker()


async def seed_db(count: int, clear: bool):
    if count > 500:
        print("Error: For safety, you cannot seed more than 500 bins at a time.")
        return

    print(f"Connecting to database...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with AsyncSessionLocal() as session:
            if clear:
                print("Clearing existing bins...")
                await session.execute(delete(SmartBin))
                await session.commit()

            print(f"Creating {count} bins...")
            for i in range(count):
                bin_id = f"BIN-{uuid.uuid4().hex[:8].upper()}-X"
                new_bin = SmartBin(
                    bin_id=bin_id,
                    capacity=100.0,
                    latitude=float(fake.latitude()),
                    longitude=float(fake.longitude()),
                    status="ACTIVE",
                )
                session.add(new_bin)

            await session.commit()
            print(f"Successfully seeded {count} bins.")
    except Exception as e:
        print(f"An error occurred while seeding: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with mock bins.")
    parser.add_argument(
        "--count", type=int, default=50, help="Number of bins to generate."
    )
    parser.add_argument(
        "--clear", action="store_true", help="Clear existing bins before seeding."
    )
    args = parser.parse_args()

    asyncio.run(seed_db(args.count, args.clear))
