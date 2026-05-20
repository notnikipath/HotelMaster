from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from shared.hotelmaster_common import (
    Property,
    PropertyType,
    Role,
    Room,
    RoomStatus,
    RoomType,
    Settings,
    TTLCache,
    auto_assign_room,
    build_audit_event,
    build_rate_breakdown,
    has_permission,
    occupancy_rate,
)

settings = Settings(service_name="room-service", service_port=8501)
app = FastAPI(title="HotelMaster Room Service", version="1.0.0")


class RoomStatusUpdateRequest(BaseModel):
    status: RoomStatus
    actor_id: str
    actor_role: Role


class ReserveRoomRequest(BaseModel):
    booking_id: str
    room_id: str
    check_in_date: date
    check_out_date: date
    actor_id: str
    actor_role: Role


class ReleaseRoomRequest(BaseModel):
    booking_id: str
    room_id: str
    actor_id: str
    actor_role: Role


class AutoAssignRequest(BaseModel):
    property_id: str
    room_type_id: str
    check_in_date: date
    check_out_date: date
    preferred_floor: int | None = None


RoomStatusUpdateRequest.model_rebuild()
ReserveRoomRequest.model_rebuild()
ReleaseRoomRequest.model_rebuild()
AutoAssignRequest.model_rebuild()


properties: dict[str, Property] = {
    "PROP-001": Property(
        property_id="PROP-001",
        name="HotelMaster City",
        property_type=PropertyType.HOTEL,
        city="Moscow",
        room_capacity=180,
    ),
    "PROP-002": Property(
        property_id="PROP-002",
        name="HotelMaster Resort",
        property_type=PropertyType.SANATORIUM,
        city="Sochi",
        room_capacity=220,
    ),
}

room_types: dict[str, RoomType] = {
    "RT-STD": RoomType(
        room_type_id="RT-STD",
        property_id="PROP-001",
        title="Standard",
        capacity=2,
        amenities=["wifi", "tv", "shower"],
        base_price=4200,
    ),
    "RT-APT": RoomType(
        room_type_id="RT-APT",
        property_id="PROP-001",
        title="Apartment",
        capacity=4,
        amenities=["wifi", "kitchen", "workspace"],
        base_price=7900,
    ),
    "RT-SPA": RoomType(
        room_type_id="RT-SPA",
        property_id="PROP-002",
        title="Wellness Suite",
        capacity=3,
        amenities=["balcony", "spa_access", "minibar"],
        base_price=9800,
    ),
}

rooms: dict[str, Room] = {}
for floor in range(1, 7):
    for idx in range(1, 11):
        room_id = f"RM-{floor:02d}{idx:02d}"
        room_type_id = "RT-STD" if idx <= 7 else "RT-APT"
        rooms[room_id] = Room(
            room_id=room_id,
            property_id="PROP-001",
            room_number=f"{floor}{idx:02d}",
            room_type_id=room_type_id,
            floor=floor,
            status=RoomStatus.AVAILABLE,
        )
for floor in range(1, 5):
    for idx in range(1, 9):
        room_id = f"RS-{floor:02d}{idx:02d}"
        rooms[room_id] = Room(
            room_id=room_id,
            property_id="PROP-002",
            room_number=f"{floor}{idx:02d}",
            room_type_id="RT-SPA",
            floor=floor,
            status=RoomStatus.AVAILABLE,
        )

# reservation_calendar[room_id] = [(booking_id, check_in_date, check_out_date)]
reservation_calendar: dict[str, list[tuple[str, date, date]]] = {}
audit_log: list[dict[str, Any]] = []
rate_cache = TTLCache(ttl_seconds=180)


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="room",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _is_overlapping(start_a: date, end_a: date, start_b: date, end_b: date) -> bool:
    return not (end_a <= start_b or end_b <= start_a)


def _is_room_available(room_id: str, check_in_date: date, check_out_date: date) -> bool:
    for _, reserved_from, reserved_to in reservation_calendar.get(room_id, []):
        if _is_overlapping(check_in_date, check_out_date, reserved_from, reserved_to):
            return False
    room = rooms.get(room_id)
    return room is not None and room.status in {RoomStatus.AVAILABLE, RoomStatus.CLEANING}


def _available_rooms(
    property_id: str,
    room_type_id: str,
    check_in_date: date,
    check_out_date: date,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for room in rooms.values():
        if room.property_id != property_id or room.room_type_id != room_type_id:
            continue
        if _is_room_available(room.room_id, check_in_date, check_out_date):
            items.append(room.model_dump(mode="json"))
    return items


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/properties")
async def list_properties(property_type: PropertyType | None = None) -> dict[str, Any]:
    items = [
        item.model_dump(mode="json")
        for item in properties.values()
        if property_type is None or item.property_type == property_type
    ]
    return {"items": items, "count": len(items)}


@app.get("/room-types")
async def list_room_types(property_id: str | None = None) -> dict[str, Any]:
    items = [
        item.model_dump(mode="json")
        for item in room_types.values()
        if property_id is None or item.property_id == property_id
    ]
    return {"items": items, "count": len(items)}


@app.get("/rooms")
async def list_rooms(
    property_id: str | None = None,
    room_type_id: str | None = None,
    status: RoomStatus | None = None,
) -> dict[str, Any]:
    items = []
    for room in rooms.values():
        if property_id and room.property_id != property_id:
            continue
        if room_type_id and room.room_type_id != room_type_id:
            continue
        if status and room.status != status:
            continue
        items.append(room.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.get("/rooms/available")
async def available_rooms(
    property_id: str,
    room_type_id: str,
    check_in_date: date,
    check_out_date: date,
) -> dict[str, Any]:
    items = _available_rooms(property_id, room_type_id, check_in_date, check_out_date)
    return {"items": items, "count": len(items)}


@app.post("/rooms/auto-assign")
async def auto_assign(request: AutoAssignRequest) -> dict[str, Any]:
    items = _available_rooms(request.property_id, request.room_type_id, request.check_in_date, request.check_out_date)
    selected = auto_assign_room(items, request.preferred_floor)
    if selected is None:
        raise HTTPException(status_code=409, detail="No room available for requested period")
    return selected


@app.post("/rooms/reserve")
async def reserve_room(request: ReserveRoomRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "room:update")
    room = rooms.get(request.room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not _is_room_available(request.room_id, request.check_in_date, request.check_out_date):
        raise HTTPException(status_code=409, detail="Room is not available in selected period")
    reservation_calendar.setdefault(request.room_id, []).append(
        (request.booking_id, request.check_in_date, request.check_out_date)
    )
    _audit(
        request.actor_id,
        request.actor_role,
        "room.reserve",
        request.room_id,
        {"booking_id": request.booking_id},
    )
    return {
        "booking_id": request.booking_id,
        "room_id": request.room_id,
        "check_in_date": request.check_in_date,
        "check_out_date": request.check_out_date,
    }


@app.post("/rooms/release")
async def release_room(request: ReleaseRoomRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "room:update")
    events = reservation_calendar.get(request.room_id, [])
    reservation_calendar[request.room_id] = [item for item in events if item[0] != request.booking_id]
    _audit(
        request.actor_id,
        request.actor_role,
        "room.release",
        request.room_id,
        {"booking_id": request.booking_id},
    )
    return {"status": "released", "booking_id": request.booking_id, "room_id": request.room_id}


@app.post("/rooms/{room_id}/status")
async def update_room_status(room_id: str, request: RoomStatusUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "room:update")
    room = rooms.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    room.status = request.status
    _audit(request.actor_id, request.actor_role, "room.status.update", room_id, {"status": request.status.value})
    return room.model_dump(mode="json")


@app.get("/rates/quote")
async def rate_quote(
    room_type_id: str,
    check_in_date: date,
    check_out_date: date,
    occupancy_ratio: float = Query(default=0.64, ge=0, le=1),
) -> dict[str, Any]:
    room_type = room_types.get(room_type_id)
    if room_type is None:
        raise HTTPException(status_code=404, detail="Room type not found")
    cache_key = f"{room_type_id}:{check_in_date}:{check_out_date}:{round(float(occupancy_ratio), 3)}"
    cached = rate_cache.get(cache_key)
    if cached is not None:
        return {"cached": True, "rate": cached}
    rate = build_rate_breakdown(room_type.base_price, check_in_date, check_out_date, float(occupancy_ratio))
    payload = rate.model_dump(mode="json")
    rate_cache.set(cache_key, payload)
    return {"cached": False, "rate": payload}


@app.get("/metrics/occupancy")
async def occupancy_metrics(property_id: str) -> dict[str, Any]:
    total = len([room for room in rooms.values() if room.property_id == property_id])
    occupied = len(
        [
            room
            for room in rooms.values()
            if room.property_id == property_id and room.status == RoomStatus.OCCUPIED
        ]
    )
    ratio = occupancy_rate(occupied, total)
    return {"property_id": property_id, "occupied_rooms": occupied, "total_rooms": total, "occupancy_rate": ratio}


@app.get("/metrics/capacity")
async def capacity_metrics() -> dict[str, Any]:
    return {
        "rooms_loaded": len(rooms),
        "target_supported_rooms": settings.max_rooms_supported,
        "target_achieved": len(rooms) <= settings.max_rooms_supported,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
