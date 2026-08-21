from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import String, Float, DateTime
from datetime import datetime
from config import get_settings

settings = get_settings()

Base = declarative_base()


class SmartBin(Base):
    """
    SQLAlchemy model representing a smart bin.

    Only static bin metadata is persisted. Dynamic simulation state
    (fill level, battery level, etc.) is maintained in memory by the
    simulator.
    """

    __tablename__ = "smart_bins"

    bin_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    zone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


# Database Async Engine
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
