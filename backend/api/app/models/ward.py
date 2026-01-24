from pydantic import BaseModel  # type: ignore
from datetime import datetime

class WardLatest(BaseModel):
    ward: int
    latitude: float
    longitude: float
    window_start: datetime
    window_end: datetime
    avg_fill_level: float


class WardHistory(BaseModel):
    window_end: datetime
    avg_fill_level: float
