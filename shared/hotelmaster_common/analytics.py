from __future__ import annotations


def occupancy_rate(occupied_rooms: int, total_rooms: int) -> float:
    if total_rooms <= 0:
        return 0.0
    return round(min(max(occupied_rooms / total_rooms, 0.0), 1.0), 4)


def adr(room_revenue: float, sold_rooms: int) -> float:
    if sold_rooms <= 0:
        return 0.0
    return round(room_revenue / sold_rooms, 2)


def revpar(room_revenue: float, total_rooms: int) -> float:
    if total_rooms <= 0:
        return 0.0
    return round(room_revenue / total_rooms, 2)
