from __future__ import annotations

import hashlib


def auto_assign_room(candidates: list[dict], preferred_floor: int | None = None) -> dict | None:
    if not candidates:
        return None
    scored = []
    for room in candidates:
        floor = int(room.get("floor", 1))
        score = 100
        if preferred_floor is not None:
            score -= abs(floor - preferred_floor) * 3
        score += 5 if room.get("status") == "available" else -20
        room_number = str(room.get("room_number", ""))
        score += 1 if room_number.endswith("01") else 0
        scored.append((score, room_number, room))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2]


def parallel_booking_plan(bookings_count: int, properties_count: int) -> dict[str, int]:
    workers = min(32, max(2, properties_count * 2, bookings_count // 120))
    chunk_size = max(25, bookings_count // max(workers, 1)) if bookings_count else 25
    return {"workers": workers, "chunk_size": chunk_size, "bookings_count": bookings_count}


def shard_for_hotel(property_id: str, shard_count: int = 8) -> int:
    if shard_count <= 0:
        return 0
    digest = hashlib.sha256(property_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % shard_count
