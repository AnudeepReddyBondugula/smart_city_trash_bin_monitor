from fastapi import APIRouter, HTTPException, Depends    # type: ignore
from sqlalchemy import text                 # type: ignore
from app.db import engine
from app.models.ward import WardLatest, WardHistory
from typing import List
from app.auth.dependencies import require_role
from app.cache.redis import get_cache, set_cache
from app.middleware.rate_limit import rate_limiter

router = APIRouter(prefix="/wards", tags=["wards"])


@router.get("/latest", response_model=List[WardLatest], dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_latest_all_wards():
    query = text("""
        SELECT l.ward,
            AVG(w.latitude) AS latitude,
            AVG(w.longitude) AS longitude,
            l.window_start,
            l.window_end,
            l.avg_fill_level
        FROM ward_latest_fill_level l
        JOIN valid_trash_bin_events w ON l.ward = w.ward
        GROUP BY l.ward, l.window_start, l.window_end, l.avg_fill_level
        ORDER BY l.ward;

    """)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    # print("rows:", rows)

    result = [dict(row) for row in rows]

    # print("Result:", result)
    return result


@router.get("/{ward_id}/latest", dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_latest_for_ward(ward_id: int):

    query = text("""
        SELECT ward, window_start, window_end, avg_fill_level
        FROM ward_latest_fill_level
        WHERE ward = :ward_id;
    """)

    with engine.connect() as conn:
        row = conn.execute(query, {"ward_id": ward_id}).mappings().first()

    if not row:
        return {
            "ward": ward_id,
            "avg_fill_level": None,
            "window_start": None,
            "window_end": None
        }
    result = dict(row)
    return result


@router.get("/{ward_id}/history", dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_ward_history(ward_id: int, hours: int = 24, limit: int = 100):
    query = text("""
        SELECT window_end, avg_fill_level
        FROM ward_fill_level_agg
        WHERE ward = :ward_id
          AND window_end >= NOW() - INTERVAL ':hours hours'
        ORDER BY window_end;
    """)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT window_end, avg_fill_level
                FROM ward_fill_level_agg
                WHERE ward = :ward_id
                AND window_end >= NOW() - (:hours || ' hours')::INTERVAL
                ORDER BY window_end DESC
                LIMIT :limit
            """),
            {
                "ward_id": ward_id,
                "hours": hours,
                "limit": limit
            }
        ).mappings().all()


    if not rows:
        return []
    return rows
