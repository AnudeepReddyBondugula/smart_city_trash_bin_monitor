from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, JSON, Text, UniqueConstraint # type: ignore
from sqlalchemy.orm import declarative_base # type: ignore

Base = declarative_base()

class ApiUser(Base):
    __tablename__ = 'api_users'

    username = Column(String(50), primary_key=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class WardBin(Base):
    __tablename__ = 'ward_bins'

    ward = Column(Integer, primary_key=True)
    bin_id = Column(String(50), primary_key=True)


class ValidTrashBinEvent(Base):
    __tablename__ = 'valid_trash_bin_events'

    bin_id = Column(String(50), primary_key=True)
    event_time = Column(DateTime(timezone=True), primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    ward = Column(Integer, nullable=False)
    fill_level = Column(Integer, nullable=False)
    temperature = Column(Float)
    humidity = Column(Integer)


class InvalidTrashBinEvent(Base):
    __tablename__ = 'invalid_trash_bin_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    bin_id = Column(String(50))
    raw_payload = Column(JSON)
    error_reason = Column(Text)
    event_time = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint('bin_id', 'event_time', name='uq_invalid_event'),
    )


class WardFillLevelAgg(Base):
    __tablename__ = 'ward_fill_level_agg'

    ward = Column(Integer, primary_key=True)
    window_start = Column(DateTime(timezone=True), primary_key=True)
    window_end = Column(DateTime(timezone=True), primary_key=True)
    avg_fill_level = Column(Float, nullable=False)


class WardFillLevelRiskAgg(Base):
    __tablename__ = 'ward_fill_level_risk_agg'

    ward = Column(Integer, primary_key=True)
    window_start = Column(DateTime(timezone=True), primary_key=True)
    window_end = Column(DateTime(timezone=True), primary_key=True)
    avg_fill_level = Column(Float, nullable=False)
    max_fill_level = Column(Integer, nullable=False)
    min_fill_level = Column(Integer, nullable=False)
    bins_above_80 = Column(Integer, nullable=False)
