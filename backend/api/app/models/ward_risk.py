from pydantic import BaseModel  # type: ignore
from datetime import datetime


class WardRiskLatest(BaseModel):
    ward: int
    avg_fill_level: float
    max_fill_level: int
    min_fill_level: int
    total_bins: int
    bins_above_80: int
    pct_bins_above_80: float
    window_end: datetime

class WardRiskHistory(BaseModel):
    window_end: datetime
    avg_fill_level: float
    max_fill_level: int
    bins_above_80: int
    pct_bins_above_80: float