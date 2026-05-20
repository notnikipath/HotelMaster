from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.hotelmaster_common import NotificationChannel, Role, Settings, has_permission

settings = Settings(service_name="notification-service", service_port=8507)
app = FastAPI(title="HotelMaster Notification Service", version="1.0.0")


class NotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    actor_role: Role


class ChatbotRequest(BaseModel):
    guest_id: str
    message: str


class CheckInReadyRequest(BaseModel):
    guest_id: str
    room_id: str
    actor_role: Role


NotificationRequest.model_rebuild()
ChatbotRequest.model_rebuild()
CheckInReadyRequest.model_rebuild()

messages: list[dict[str, Any]] = []
chat_history: list[dict[str, Any]] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send_notification(request: NotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": request.channel.value,
        "recipient": request.recipient,
        "subject": request.subject,
        "body": request.body,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
    messages.append(payload)
    return payload


@app.post("/notify/checkin-ready")
async def notify_checkin_ready(request: CheckInReadyRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.PUSH.value,
        "recipient": request.guest_id,
        "subject": "Room is ready",
        "body": f"Your room {request.room_id} is prepared and ready for check-in.",
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
    messages.append(payload)
    return payload


@app.post("/chatbot")
async def chatbot(request: ChatbotRequest) -> dict[str, Any]:
    normalized = request.message.lower()
    answer = "Please contact reception for details."
    if "wifi" in normalized:
        answer = "Wi-Fi network: HotelMaster_Guest, password: welcome2026"
    elif "breakfast" in normalized:
        answer = "Breakfast is served from 07:00 to 11:00 in the restaurant."
    elif "spa" in normalized:
        answer = "Spa is open from 09:00 to 22:00."
    elif "transfer" in normalized:
        answer = "Transfer can be ordered at least 2 hours before departure."

    payload = {
        "guest_id": request.guest_id,
        "message": request.message,
        "answer": answer,
        "created_at": datetime.now(UTC).isoformat(),
    }
    chat_history.append(payload)
    return payload


@app.get("/notify/history")
async def history() -> dict[str, Any]:
    return {"items": messages, "count": len(messages)}


@app.get("/chatbot/history")
async def chatbot_history() -> dict[str, Any]:
    return {"items": chat_history, "count": len(chat_history)}
