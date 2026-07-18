from database import engine, Base
import asyncio


async def create_tables() -> None:
    """
    Creates all database tables if they do not exists
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created (if they did not already exist).")

    await engine.dispose()


async def main() -> None:
    try:
        await create_tables()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
