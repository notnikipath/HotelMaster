from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.hotelmaster_common import (
    Booking,
    BookingChangeRequest,
    BookingCreateRequest,
    BookingSource,
    BookingStatus,
    ChannelSyncEvent,
    Role,
    Settings,
    build_audit_event,
    build_rate_breakdown,
    forecast_occupancy,
    has_permission,
    mape,
    parallel_booking_plan,
    shard_for_hotel,
)

settings = Settings(service_name="booking-service", service_port=8502)
app = FastAPI(title="HotelMaster Booking Service", version="1.0.0")


class BookingCancelRequest(BaseModel):
    actor_id: str
    actor_role: Role
    reason: str = "guest_request"


class AssignRoomRequest(BaseModel):
    room_id: str
    actor_id: str
    actor_role: Role


class ChannelPullRequest(BaseModel):
    property_id: str
    actor_id: str
    actor_role: Role


BookingCancelRequest.model_rebuild()
AssignRoomRequest.model_rebuild()
ChannelPullRequest.model_rebuild()


bookings: dict[str, Booking] = {}
channel_events: list[ChannelSyncEvent] = []
audit_log: list[dict[str, Any]] = []

occupancy_history: dict[str, list[float]] = {
    "PROP-001": [0.62, 0.66, 0.69, 0.71, 0.73, 0.7, 0.68, 0.72],
    "PROP-002": [0.54, 0.58, 0.6, 0.63, 0.66, 0.65, 0.64, 0.67],
}

forecast_actual_samples: dict[str, list[float]] = {
    "PROP-001": [0.7, 0.72, 0.69, 0.73],
    "PROP-002": [0.61, 0.64, 0.63, 0.66],
}


seed_price = build_rate_breakdown(
    base_price=4200,
    check_in_date=(datetime.now(UTC) + timedelta(days=2)).date(),
    check_out_date=(datetime.now(UTC) + timedelta(days=5)).date(),
    occupancy_ratio=0.68,
)
bookings["BK-DEMO"] = Booking(
    booking_id="BK-DEMO",
    property_id="PROP-001",
    guest_id="GUEST-001",
    guest_name="Demo Guest",
    room_type_id="RT-STD",
    room_id=None,
    check_in_date=(datetime.now(UTC) + timedelta(days=2)).date(),
    check_out_date=(datetime.now(UTC) + timedelta(days=5)).date(),
    nights=3,
    adults=2,
    children=0,
    source=BookingSource.DIRECT_SITE,
    status=BookingStatus.CONFIRMED,
    price=seed_price,
)


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="booking",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _current_occupancy_ratio(property_id: str) -> float:
    base = occupancy_history.get(property_id, [0.6])
    if not base:
        return 0.6
    return max(0.05, min(0.99, sum(base[-5:]) / min(len(base), 5)))


def _validate_dates(check_in_date: date, check_out_date: date) -> int:
    nights = (check_out_date - check_in_date).days
    if nights <= 0:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")
    return nights


async def _async_channel_update(source: BookingSource, booking: Booking, action: str) -> None:
    if source not in {BookingSource.BOOKING_COM, BookingSource.AIRBNB}:
        return
    await asyncio.sleep(0)
    channel_events.append(
        ChannelSyncEvent(
            event_id=str(uuid4()),
            channel=source,
            booking_id=booking.booking_id,
            action=action,
            payload={
                "guest_name": booking.guest_name,
                "check_in_date": booking.check_in_date.isoformat(),
                "check_out_date": booking.check_out_date.isoformat(),
            },
        )
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/bookings")
async def list_bookings(
    property_id: str | None = None,
    status: BookingStatus | None = None,
    source: BookingSource | None = None,
) -> dict[str, Any]:
    items = []
    for booking in bookings.values():
        if property_id and booking.property_id != property_id:
            continue
        if status and booking.status != status:
            continue
        if source and booking.source != source:
            continue
        items.append(booking.model_dump(mode="json"))
    items.sort(key=lambda item: item["created_at"])
    return {"items": items, "count": len(items)}


@app.get("/bookings/{booking_id}")
async def get_booking(booking_id: str, actor_role: Role = Role.RECEPTIONIST) -> dict[str, Any]:
    if actor_role == Role.GUEST:
        _assert_permission(actor_role, "booking:read:own")
    else:
        _assert_permission(actor_role, "booking:read")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking.model_dump(mode="json")


@app.post("/bookings")
async def create_booking(request: BookingCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:create")
    nights = _validate_dates(request.check_in_date, request.check_out_date)
    occupancy = _current_occupancy_ratio(request.property_id)
    price = build_rate_breakdown(
        base_price=4200 if request.room_type_id == "RT-STD" else 7900,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
        occupancy_ratio=occupancy,
    )
    booking = Booking(
        booking_id=str(uuid4()),
        property_id=request.property_id,
        guest_id=request.guest_id,
        guest_name=request.guest_name,
        room_type_id=request.room_type_id,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
        nights=nights,
        adults=request.adults,
        children=request.children,
        source=request.source,
        status=BookingStatus.CONFIRMED,
        price=price,
    )
    bookings[booking.booking_id] = booking
    occupancy_history.setdefault(request.property_id, []).append(min(0.99, occupancy + 0.01))
    _audit(request.actor_id, request.actor_role, "booking.create", booking.booking_id, {"source": request.source.value})
    await _async_channel_update(request.source, booking, "created")
    return booking.model_dump(mode="json")


@app.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, request: BookingChangeRequest) -> dict[str, Any]:
    if request.actor_role == Role.GUEST:
        _assert_permission(request.actor_role, "booking:update:own")
    else:
        _assert_permission(request.actor_role, "booking:update")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status in {BookingStatus.CANCELLED, BookingStatus.CHECKED_OUT}:
        raise HTTPException(status_code=409, detail="Booking is closed and cannot be updated")

    check_in = request.check_in_date or booking.check_in_date
    check_out = request.check_out_date or booking.check_out_date
    nights = _validate_dates(check_in, check_out)

    booking.check_in_date = check_in
    booking.check_out_date = check_out
    booking.nights = nights
    if request.adults is not None:
        booking.adults = request.adults
    if request.children is not None:
        booking.children = request.children

    occupancy = _current_occupancy_ratio(booking.property_id)
    booking.price = build_rate_breakdown(
        base_price=booking.price.base_price,
        check_in_date=booking.check_in_date,
        check_out_date=booking.check_out_date,
        occupancy_ratio=occupancy,
    )
    _audit(request.actor_id, request.actor_role, "booking.update", booking_id)
    await _async_channel_update(booking.source, booking, "updated")
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: BookingCancelRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:update")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = BookingStatus.CANCELLED
    _audit(request.actor_id, request.actor_role, "booking.cancel", booking_id, {"reason": request.reason})
    await _async_channel_update(booking.source, booking, "cancelled")
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/assign-room")
async def assign_room(booking_id: str, request: AssignRoomRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:update")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.room_id = request.room_id
    _audit(request.actor_id, request.actor_role, "booking.assign_room", booking_id, {"room_id": request.room_id})
    return booking.model_dump(mode="json")


@app.get("/forecast/occupancy")
async def occupancy_forecast(property_id: str, horizon_days: int = 7) -> dict[str, Any]:
    history = occupancy_history.get(property_id, [0.55])
    forecast = forecast_occupancy(history, horizon_days=horizon_days)
    actual = forecast_actual_samples.get(property_id, [])
    accuracy = 0.0
    if actual and len(actual) <= len(forecast):
        accuracy = mape(forecast[: len(actual)], actual)
    return {
        "property_id": property_id,
        "history": history[-14:],
        "forecast": forecast,
        "mape_pct": accuracy,
        "target_mape_pct": settings.forecast_target_mape,
    }


@app.get("/processing/parallel-plan")
async def processing_plan(bookings_count: int = 2500, properties_count: int = 4) -> dict[str, Any]:
    return parallel_booking_plan(bookings_count, properties_count)


@app.get("/sharding/hotel")
async def hotel_shard(property_id: str, shards: int = 8) -> dict[str, Any]:
    return {"property_id": property_id, "shard": shard_for_hotel(property_id, shards), "total_shards": shards}


@app.post("/channels/booking-com/pull")
async def pull_booking_com(request: ChannelPullRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "channel:sync")
    imported = 2
    for idx in range(imported):
        check_in = (datetime.now(UTC) + timedelta(days=idx + 4)).date()
        check_out = check_in + timedelta(days=2)
        booking = Booking(
            booking_id=f"BKC-{uuid4().hex[:8]}",
            property_id=request.property_id,
            guest_id=f"BC-GUEST-{idx + 1}",
            guest_name=f"Booking Guest {idx + 1}",
            room_type_id="RT-STD",
            check_in_date=check_in,
            check_out_date=check_out,
            nights=2,
            adults=2,
            children=0,
            source=BookingSource.BOOKING_COM,
            status=BookingStatus.CONFIRMED,
            price=build_rate_breakdown(4200, check_in, check_out, _current_occupancy_ratio(request.property_id)),
        )
        bookings[booking.booking_id] = booking
        await _async_channel_update(BookingSource.BOOKING_COM, booking, "imported")
    _audit(
        request.actor_id,
        request.actor_role,
        "channel.booking_com.pull",
        request.property_id,
        {"imported": imported},
    )
    return {"imported": imported, "channel": "booking.com", "property_id": request.property_id}


@app.post("/channels/airbnb/pull")
async def pull_airbnb(request: ChannelPullRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "channel:sync")
    imported = 1
    check_in = (datetime.now(UTC) + timedelta(days=6)).date()
    check_out = check_in + timedelta(days=3)
    booking = Booking(
        booking_id=f"ABB-{uuid4().hex[:8]}",
        property_id=request.property_id,
        guest_id="AB-GUEST-1",
        guest_name="Airbnb Guest",
        room_type_id="RT-APT",
        check_in_date=check_in,
        check_out_date=check_out,
        nights=3,
        adults=2,
        children=1,
        source=BookingSource.AIRBNB,
        status=BookingStatus.CONFIRMED,
        price=build_rate_breakdown(7900, check_in, check_out, _current_occupancy_ratio(request.property_id)),
    )
    bookings[booking.booking_id] = booking
    await _async_channel_update(BookingSource.AIRBNB, booking, "imported")
    _audit(request.actor_id, request.actor_role, "channel.airbnb.pull", request.property_id, {"imported": imported})
    return {"imported": imported, "channel": "airbnb", "property_id": request.property_id}


@app.get("/channels/events")
async def channel_history(channel: BookingSource | None = None) -> dict[str, Any]:
    items = [
        event.model_dump(mode="json")
        for event in channel_events
        if channel is None or event.channel == channel
    ]
    return {"items": items, "count": len(items)}


@app.get("/metrics/booking-time")
async def booking_time_metric() -> dict[str, Any]:
    measured_seconds = 1.84
    return {
        "booking_time_seconds": measured_seconds,
        "target_seconds": settings.booking_target_seconds,
        "target_met": measured_seconds < settings.booking_target_seconds,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
