from fastapi import APIRouter, Depends      # type: ignore
from sqlalchemy import text                 # type: ignore
from typing import List 
from app.db import engine
from app.models.ward_risk import WardRiskLatest, WardRiskHistory  
from app.auth.dependencies import require_role

router = APIRouter(prefix="/wards", tags=["Ward Risk"])


@router.get("/latest/risk", response_model=List[WardRiskLatest], dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_latest_ward_risk(hours: int = 24):
    query = text("""
        SELECT
            r.ward,
            r.avg_fill_level,
            r.max_fill_level,
            r.min_fill_level,
            5 AS total_bins,  -- fixed per ward
            COUNT(DISTINCT CASE WHEN e.fill_level > 80 THEN e.bin_id END) AS bins_above_80,
            ROUND(
                (COUNT(DISTINCT CASE WHEN e.fill_level > 80 THEN e.bin_id END)::numeric / 5) * 100,
                2
            ) AS pct_bins_above_80,
            r.window_end
        FROM ward_fill_level_risk_agg r
        JOIN valid_trash_bin_events e
        ON r.ward = e.ward
        AND e.event_time BETWEEN r.window_end - interval '1 hour' AND r.window_end
        WHERE r.window_end = (
            SELECT MAX(r2.window_end)
            FROM ward_fill_level_risk_agg r2
            WHERE r2.ward = r.ward
        )
        GROUP BY r.ward, r.avg_fill_level, r.max_fill_level, r.min_fill_level, r.window_end
        ORDER BY r.ward;
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"hours": hours}).mappings().all()
    # print("rows:", rows)
    
    return [dict(row) for row in rows]



@router.get("/{ward_id}/risk/history", dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_risk_history(ward_id: int, hours: int = 24):
    query = text("""
        SELECT
            r.ward,
            r.window_end,
            r.avg_fill_level,
            r.max_fill_level,
            r.min_fill_level,
            5 AS total_bins,  -- fixed value per ward
            r.bins_above_80,
            ROUND((r.bins_above_80::numeric / 5) * 100, 2) AS pct_bins_above_80
        FROM ward_fill_level_risk_agg r
        WHERE r.ward = :ward_id
        AND r.window_end >= NOW() - (:hours * interval '1 hour')
        ORDER BY r.window_end DESC;
    """)

    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "ward_id": ward_id,
                "hours": hours
            }
        ).mappings().all()
    return rows



@router.get("/risky", response_model=List[WardRiskLatest], dependencies=[Depends(require_role(["viewer", "admin"]))])
def get_risky_wards():
    query = text("""
        SELECT
            r.ward,
            r.avg_fill_level,
            r.max_fill_level,
            r.min_fill_level,
            5 AS total_bins,
            r.bins_above_80,
            ROUND((r.bins_above_80::numeric / 5) * 100, 2) AS pct_bins_above_80,
            r.window_end
        FROM ward_fill_level_risk_agg r
        WHERE r.bins_above_80 > 0
        AND r.window_end = (
            SELECT MAX(r2.window_end)
            FROM ward_fill_level_risk_agg r2
            WHERE r2.ward = r.ward
        )
        ORDER BY r.ward;
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    result = [dict(row) for row in rows]
    return result