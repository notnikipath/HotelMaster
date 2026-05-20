from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.hotelmaster_common import CheckInWorkflowResult, Role, Settings, sign_token, verify_token


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8500

    room_service_url: str = "http://room-service:8501"
    booking_service_url: str = "http://booking-service:8502"
    frontdesk_service_url: str = "http://frontdesk-service:8503"
    housekeeping_service_url: str = "http://housekeeping-service:8504"
    extra_service_url: str = "http://extra-service:8505"
    reports_service_url: str = "http://reports-service:8506"
    notification_service_url: str = "http://notification-service:8507"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="HotelMaster API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role


class CheckInWorkflowRequest(BaseModel):
    booking_id: str
    deposit_amount: float = Field(default=0, ge=0)
    preferred_floor: int | None = None
    actor_id: str
    actor_role: Role


class CheckOutWorkflowRequest(BaseModel):
    stay_id: str
    actor_id: str
    actor_role: Role


AuthRequest.model_rebuild()
CheckInWorkflowRequest.model_rebuild()
CheckOutWorkflowRequest.model_rebuild()


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "room": settings.room_service_url,
        "booking": settings.booking_service_url,
        "frontdesk": settings.frontdesk_service_url,
        "housekeeping": settings.housekeeping_service_url,
        "extra": settings.extra_service_url,
        "reports": settings.reports_service_url,
        "notification": settings.notification_service_url,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except HTTPException as exc:
                statuses[name] = {"status": "error", "detail": exc.detail}
            except httpx.HTTPError as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.post("/workflow/check-in")
async def check_in_workflow(request: CheckInWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        booking = await _get_json(
            client,
            f"{settings.booking_service_url}/bookings/{request.booking_id}",
            {"actor_role": request.actor_role.value},
        )

        room = await _post_json(
            client,
            f"{settings.room_service_url}/rooms/auto-assign",
            {
                "property_id": booking["property_id"],
                "room_type_id": booking["room_type_id"],
                "check_in_date": booking["check_in_date"],
                "check_out_date": booking["check_out_date"],
                "preferred_floor": request.preferred_floor,
            },
        )

        await _post_json(
            client,
            f"{settings.room_service_url}/rooms/reserve",
            {
                "booking_id": booking["booking_id"],
                "room_id": room["room_id"],
                "check_in_date": booking["check_in_date"],
                "check_out_date": booking["check_out_date"],
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{settings.booking_service_url}/bookings/{request.booking_id}/assign-room",
            {
                "room_id": room["room_id"],
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        assigned_booking = await _get_json(
            client,
            f"{settings.booking_service_url}/bookings/{request.booking_id}",
            {"actor_role": request.actor_role.value},
        )

        await _post_json(
            client,
            f"{settings.room_service_url}/rooms/{room['room_id']}/status",
            {
                "status": "occupied",
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        stay = await _post_json(
            client,
            f"{settings.frontdesk_service_url}/check-in",
            {
                "booking_id": booking["booking_id"],
                "guest_id": booking["guest_id"],
                "room_id": room["room_id"],
                "deposit_amount": request.deposit_amount,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        prep_task = await _post_json(
            client,
            f"{settings.housekeeping_service_url}/prepare-room",
            {
                "property_id": booking["property_id"],
                "room_id": room["room_id"],
            },
        )

        await _post_json(
            client,
            f"{settings.notification_service_url}/notify/checkin-ready",
            {
                "guest_id": booking["guest_id"],
                "room_id": room["room_id"],
                "actor_role": request.actor_role.value,
            },
        )

    result = CheckInWorkflowResult(
        booking=assigned_booking,
        assigned_room=room,
        stay=stay,
        prep_task=prep_task,
    )
    return result.model_dump(mode="json")


@app.post("/workflow/check-out")
async def check_out_workflow(request: CheckOutWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        stay_payload = await _get_json(client, f"{settings.frontdesk_service_url}/stays/{request.stay_id}")
        charges = await _get_json(client, f"{settings.extra_service_url}/charges", {"stay_id": request.stay_id})

        charges_total = round(sum(item["amount"] for item in charges.get("items", [])), 2)
        if charges_total > 0:
            await _post_json(
                client,
                f"{settings.frontdesk_service_url}/stays/add-extra",
                {
                    "stay_id": request.stay_id,
                    "amount": charges_total,
                    "actor_id": request.actor_id,
                    "actor_role": request.actor_role.value,
                },
            )

        checkout = await _post_json(
            client,
            f"{settings.frontdesk_service_url}/check-out",
            {
                "stay_id": request.stay_id,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{settings.room_service_url}/rooms/{stay_payload['room_id']}/status",
            {
                "status": "cleaning",
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

    return {"checkout": checkout, "charges_total": charges_total}


@app.get("/dashboard/{property_id}")
async def dashboard(property_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        operational = await _get_json(
            client,
            f"{settings.reports_service_url}/reports/operational",
            {"property_id": property_id},
        )
        financial = await _get_json(
            client,
            f"{settings.reports_service_url}/reports/financial",
            {"property_id": property_id},
        )
        forecast = await _get_json(
            client,
            f"{settings.booking_service_url}/forecast/occupancy",
            {"property_id": property_id},
        )
        booking_time = await _get_json(client, f"{settings.booking_service_url}/metrics/booking-time")
        tasks = await _get_json(client, f"{settings.housekeeping_service_url}/tasks", {"property_id": property_id})
        bookings = await _get_json(client, f"{settings.booking_service_url}/bookings", {"property_id": property_id})

    return {
        "property_id": property_id,
        "operational": operational,
        "financial": financial,
        "forecast": forecast,
        "booking_time": booking_time,
        "housekeeping": tasks,
        "bookings": bookings,
    }
