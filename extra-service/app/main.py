from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.hotelmaster_common import ExtraCharge, ExtraChargeRequest, Role, ServiceType, Settings, has_permission

settings = Settings(service_name="extra-service", service_port=8505)
app = FastAPI(title="HotelMaster Extra Service", version="1.0.0")

charges: dict[str, ExtraCharge] = {
    "CHG-DEMO": ExtraCharge(
        charge_id="CHG-DEMO",
        stay_id="STAY-DEMO",
        service_type=ServiceType.RESTAURANT,
        title="Breakfast buffet",
        amount=1800,
    )
}

audit_log: list[dict[str, Any]] = []

service_catalog = {
    ServiceType.RESTAURANT.value: [
        {"sku": "DINNER", "title": "Dinner", "price": 2400},
        {"sku": "BREAKFAST", "title": "Breakfast", "price": 900},
    ],
    ServiceType.SPA.value: [
        {"sku": "MASSAGE", "title": "Massage", "price": 4200},
        {"sku": "POOL", "title": "Pool access", "price": 1300},
    ],
    ServiceType.TRANSFER.value: [
        {"sku": "AIRPORT", "title": "Airport transfer", "price": 2900},
    ],
}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/catalog")
async def catalog(service_type: ServiceType | None = None) -> dict[str, Any]:
    if service_type is not None:
        return {"service_type": service_type.value, "items": service_catalog.get(service_type.value, [])}
    return {"items": service_catalog}


@app.post("/charges")
async def add_charge(request: ExtraChargeRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "extra:create")
    charge = ExtraCharge(
        charge_id=str(uuid4()),
        stay_id=request.stay_id,
        service_type=request.service_type,
        title=request.title,
        amount=request.amount,
    )
    charges[charge.charge_id] = charge
    audit_log.append(
        {
            "event_id": str(uuid4()),
            "action": "extra.charge.create",
            "actor_id": request.actor_id,
            "actor_role": request.actor_role.value,
            "charge_id": charge.charge_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return charge.model_dump(mode="json")


@app.get("/charges")
async def list_charges(stay_id: str | None = None, service_type: ServiceType | None = None) -> dict[str, Any]:
    items = []
    for charge in charges.values():
        if stay_id and charge.stay_id != stay_id:
            continue
        if service_type and charge.service_type != service_type:
            continue
        items.append(charge.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.get("/charges/{charge_id}")
async def get_charge(charge_id: str) -> dict[str, Any]:
    charge = charges.get(charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    return charge.model_dump(mode="json")


@app.post("/integrations/fiscal/receipt")
async def fiscal_receipt(stay_id: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "extra:read")
    total = round(sum(charge.amount for charge in charges.values() if charge.stay_id == stay_id), 2)
    return {
        "receipt_id": str(uuid4()),
        "stay_id": stay_id,
        "total": total,
        "currency": "RUB",
        "fiscal_device": "ATOL-55F",
        "status": "printed",
        "actor_id": actor_id,
    }


@app.post("/integrations/smart-room/command")
async def smart_room_command(room_id: str, command: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "extra:read")
    return {
        "room_id": room_id,
        "command": command,
        "channel": "iot",
        "status": "accepted",
        "actor_id": actor_id,
        "processed_at": datetime.now(UTC).isoformat(),
    }


@app.post("/voice-assistant")
async def voice_assistant(room_id: str, phrase: str) -> dict[str, Any]:
    normalized = phrase.lower()
    action = "help"
    if "lights" in normalized or "свет" in normalized:
        action = "toggle_lights"
    elif "temperature" in normalized or "темпера" in normalized:
        action = "adjust_temperature"
    elif "clean" in normalized or "убор" in normalized:
        action = "request_cleaning"
    return {
        "room_id": room_id,
        "phrase": phrase,
        "action": action,
        "status": "interpreted",
    }


@app.get("/audit")
async def get_audit(limit: int = 100) -> dict[str, Any]:
    return {"items": audit_log[-limit:]}
