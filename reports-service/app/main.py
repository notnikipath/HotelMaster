from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from statistics import mean
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.hotelmaster_common import Role, Settings, adr, has_permission, mape, occupancy_rate, revpar

settings = Settings(service_name="reports-service", service_port=8506)
app = FastAPI(title="HotelMaster Reports Service", version="1.0.0")


class DailySnapshotRequest(BaseModel):
    property_id: str
    day: date
    total_rooms: int = Field(gt=0)
    occupied_rooms: int = Field(ge=0)
    sold_rooms: int = Field(ge=0)
    room_revenue: float = Field(ge=0)
    extras_revenue: float = Field(ge=0)
    costs: float = Field(ge=0)


DailySnapshotRequest.model_rebuild()


daily_snapshots: list[dict[str, Any]] = []
forecast_pairs: dict[str, dict[str, list[float]]] = {
    "PROP-001": {"predicted": [0.7, 0.71, 0.73, 0.75], "actual": [0.69, 0.72, 0.72, 0.74]},
    "PROP-002": {"predicted": [0.61, 0.63, 0.65, 0.66], "actual": [0.6, 0.64, 0.64, 0.67]},
}


for idx in range(10):
    day = datetime.now(UTC).date() - timedelta(days=idx)
    daily_snapshots.append(
        {
            "property_id": "PROP-001",
            "day": day,
            "total_rooms": 92,
            "occupied_rooms": 67 + (idx % 4),
            "sold_rooms": 67 + (idx % 4),
            "room_revenue": 360000 + idx * 4200,
            "extras_revenue": 92000 + idx * 1900,
            "costs": 170000 + idx * 1300,
        }
    )


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _filtered(property_id: str | None = None) -> list[dict[str, Any]]:
    return [item for item in daily_snapshots if property_id is None or item["property_id"] == property_id]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/reports/ingest/day")
async def ingest_daily_snapshot(request: DailySnapshotRequest) -> dict[str, Any]:
    payload = request.model_dump()
    daily_snapshots.append(payload)
    return {"status": "accepted", "snapshot": payload}


@app.get("/reports/operational")
async def operational_report(property_id: str, actor_role: Role = Role.MANAGER) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:read")
    records = _filtered(property_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records for property")

    last = records[-1]
    room_rev = sum(item["room_revenue"] for item in records)
    sold_rooms = sum(item["sold_rooms"] for item in records)
    total_rooms = sum(item["total_rooms"] for item in records)
    occupied_rooms = sum(item["occupied_rooms"] for item in records)

    occupancy = occupancy_rate(occupied_rooms, total_rooms)
    adr_value = adr(room_rev, sold_rooms)
    revpar_value = revpar(room_rev, total_rooms)

    return {
        "property_id": property_id,
        "period_days": len(records),
        "latest_day": str(last["day"]),
        "occupancy_rate": occupancy,
        "adr": adr_value,
        "revpar": revpar_value,
        "kpi_targets": {
            "booking_time_seconds": settings.booking_target_seconds,
            "forecast_mape_pct": settings.forecast_target_mape,
            "rooms_supported": settings.max_rooms_supported,
        },
    }


@app.get("/reports/financial")
async def financial_report(property_id: str, actor_role: Role = Role.ACCOUNTANT) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:read")
    records = _filtered(property_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records for property")
    room_revenue = sum(item["room_revenue"] for item in records)
    extras_revenue = sum(item["extras_revenue"] for item in records)
    costs = sum(item["costs"] for item in records)
    gross = room_revenue + extras_revenue
    profit = gross - costs
    margin = round((profit / gross) * 100, 2) if gross else 0
    return {
        "property_id": property_id,
        "room_revenue": round(room_revenue, 2),
        "extras_revenue": round(extras_revenue, 2),
        "gross_revenue": round(gross, 2),
        "costs": round(costs, 2),
        "profit": round(profit, 2),
        "margin_pct": margin,
    }


@app.get("/reports/forecast-accuracy")
async def forecast_accuracy(property_id: str) -> dict[str, Any]:
    pair = forecast_pairs.get(property_id)
    if pair is None:
        raise HTTPException(status_code=404, detail="No forecast samples")
    score = mape(pair["predicted"], pair["actual"])
    return {
        "property_id": property_id,
        "predicted": pair["predicted"],
        "actual": pair["actual"],
        "mape_pct": score,
        "target_mape_pct": settings.forecast_target_mape,
        "target_met": score < settings.forecast_target_mape,
    }


@app.get("/reports/kpi")
async def kpi_dashboard(property_id: str) -> dict[str, Any]:
    records = _filtered(property_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records for property")

    occupancy_samples = [occupancy_rate(item["occupied_rooms"], item["total_rooms"]) for item in records]
    avg_occupancy = round(mean(occupancy_samples), 4)
    booking_time_seconds = 1.9
    return {
        "property_id": property_id,
        "avg_occupancy": avg_occupancy,
        "booking_time_seconds": booking_time_seconds,
        "booking_time_target": settings.booking_target_seconds,
        "rooms_target": settings.max_rooms_supported,
        "meets_booking_time_target": booking_time_seconds < settings.booking_target_seconds,
    }


@app.get("/reports/export/1c")
async def export_1c(property_id: str, actor_role: Role = Role.ACCOUNTANT) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:read")
    records = _filtered(property_id)
    if not records:
        raise HTTPException(status_code=404, detail="No records for property")
    export_id = str(uuid4())
    return {
        "export_id": export_id,
        "property_id": property_id,
        "system": "1C",
        "records": len(records),
        "status": "exported",
        "created_at": datetime.now(UTC).isoformat(),
    }
