from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.hotelmaster_common import FrontdeskStay, Role, Settings, build_audit_event, has_permission

settings = Settings(service_name="frontdesk-service", service_port=8503)
app = FastAPI(title="HotelMaster Frontdesk Service", version="1.0.0")


class OpenStayRequest(BaseModel):
    booking_id: str
    guest_id: str
    room_id: str
    deposit_amount: float = Field(default=0, ge=0)
    actor_id: str
    actor_role: Role


class CloseStayRequest(BaseModel):
    stay_id: str
    actor_id: str
    actor_role: Role


class AddExtraToStayRequest(BaseModel):
    stay_id: str
    amount: float = Field(gt=0)
    actor_id: str
    actor_role: Role


class DocumentPrintRequest(BaseModel):
    stay_id: str
    document_type: str = "registration_card"
    actor_id: str
    actor_role: Role


class SelfCheckInRequest(BaseModel):
    booking_id: str
    guest_id: str
    passport_suffix: str = Field(min_length=4, max_length=4)


OpenStayRequest.model_rebuild()
CloseStayRequest.model_rebuild()
AddExtraToStayRequest.model_rebuild()
DocumentPrintRequest.model_rebuild()
SelfCheckInRequest.model_rebuild()


stays: dict[str, FrontdeskStay] = {
    "STAY-DEMO": FrontdeskStay(
        stay_id="STAY-DEMO",
        booking_id="BK-DEMO",
        guest_id="GUEST-001",
        room_id="RM-0101",
        check_in_at=datetime.now(UTC),
        deposit_amount=5000,
        extras_total=1800,
        status="active",
    )
}
audit_log: list[dict[str, Any]] = []
printed_docs: list[dict[str, Any]] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="frontdesk",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/stays")
async def list_stays(status: str | None = None) -> dict[str, Any]:
    items = [
        stay.model_dump(mode="json")
        for stay in stays.values()
        if status is None or stay.status == status
    ]
    return {"items": items, "count": len(items)}


@app.get("/stays/{stay_id}")
async def get_stay(stay_id: str) -> dict[str, Any]:
    stay = stays.get(stay_id)
    if stay is None:
        raise HTTPException(status_code=404, detail="Stay not found")
    return stay.model_dump(mode="json")


@app.post("/check-in")
async def check_in(request: OpenStayRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "frontdesk:checkin")
    stay = FrontdeskStay(
        stay_id=str(uuid4()),
        booking_id=request.booking_id,
        guest_id=request.guest_id,
        room_id=request.room_id,
        deposit_amount=request.deposit_amount,
        status="active",
    )
    stays[stay.stay_id] = stay
    _audit(request.actor_id, request.actor_role, "frontdesk.check_in", stay.stay_id, {"booking_id": request.booking_id})
    return stay.model_dump(mode="json")


@app.post("/check-out")
async def check_out(request: CloseStayRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "frontdesk:checkout")
    stay = stays.get(request.stay_id)
    if stay is None:
        raise HTTPException(status_code=404, detail="Stay not found")
    stay.check_out_at = datetime.now(UTC)
    stay.status = "closed"
    total_due = round(stay.extras_total, 2)
    refund = round(max(stay.deposit_amount - total_due, 0), 2)
    _audit(request.actor_id, request.actor_role, "frontdesk.check_out", stay.stay_id, {"refund": refund})
    return {
        "stay": stay.model_dump(mode="json"),
        "invoice": {
            "deposit": stay.deposit_amount,
            "extras_total": stay.extras_total,
            "room_total": 0,
            "total_due": total_due,
            "refund": refund,
        },
    }


@app.post("/stays/add-extra")
async def add_extra_to_stay(request: AddExtraToStayRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "extra:create")
    stay = stays.get(request.stay_id)
    if stay is None:
        raise HTTPException(status_code=404, detail="Stay not found")
    stay.extras_total = round(stay.extras_total + request.amount, 2)
    _audit(request.actor_id, request.actor_role, "frontdesk.add_extra", stay.stay_id, {"amount": request.amount})
    return stay.model_dump(mode="json")


@app.post("/documents/print")
async def print_document(request: DocumentPrintRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "frontdesk:checkin")
    stay = stays.get(request.stay_id)
    if stay is None:
        raise HTTPException(status_code=404, detail="Stay not found")
    payload = {
        "document_id": str(uuid4()),
        "stay_id": request.stay_id,
        "document_type": request.document_type,
        "printed_at": datetime.now(UTC).isoformat(),
        "content": f"Document {request.document_type} for stay {request.stay_id}",
    }
    printed_docs.append(payload)
    _audit(request.actor_id, request.actor_role, "frontdesk.print_document", request.stay_id)
    return payload


@app.post("/self-checkin/session")
async def self_checkin_session(request: SelfCheckInRequest) -> dict[str, Any]:
    session_id = str(uuid4())
    return {
        "session_id": session_id,
        "booking_id": request.booking_id,
        "guest_id": request.guest_id,
        "kiosk_enabled": True,
        "status": "identity_verified" if request.passport_suffix.isdigit() else "manual_review",
    }


@app.get("/documents/history")
async def documents_history() -> dict[str, Any]:
    return {"items": printed_docs, "count": len(printed_docs)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
