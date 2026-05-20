from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    APART_HOTEL = "apart_hotel"
    SANATORIUM = "sanatorium"


class RoomStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"


class BookingSource(str, Enum):
    DIRECT_SITE = "direct_site"
    BOOKING_COM = "booking_com"
    AIRBNB = "airbnb"
    WALK_IN = "walk_in"


class BookingStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    NO_SHOW = "no_show"


class TaskType(str, Enum):
    CLEANING = "cleaning"
    REPAIR = "repair"
    PREPARE_ROOM = "prepare_room"


class TaskStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ServiceType(str, Enum):
    RESTAURANT = "restaurant"
    SPA = "spa"
    TRANSFER = "transfer"
    LAUNDRY = "laundry"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"


class Role(str, Enum):
    GUEST = "guest"
    RECEPTIONIST = "receptionist"
    MANAGER = "manager"
    HOUSEKEEPING = "housekeeping"
    ACCOUNTANT = "accountant"
    ADMIN = "admin"


class Property(BaseModel):
    property_id: str
    name: str
    property_type: PropertyType
    city: str
    room_capacity: int = Field(gt=0)


class RoomType(BaseModel):
    room_type_id: str
    property_id: str
    title: str
    capacity: int = Field(gt=0)
    amenities: list[str] = Field(default_factory=list)
    base_price: float = Field(gt=0)


class Room(BaseModel):
    room_id: str
    property_id: str
    room_number: str
    room_type_id: str
    floor: int = 1
    status: RoomStatus = RoomStatus.AVAILABLE


class RateBreakdown(BaseModel):
    base_price: float = Field(ge=0)
    season_factor: float = Field(ge=0)
    occupancy_factor: float = Field(ge=0)
    lead_time_factor: float = Field(ge=0)
    nightly_rate: float = Field(ge=0)
    nights: int = Field(gt=0)
    total_amount: float = Field(ge=0)
    currency: str = "RUB"


class BookingCreateRequest(BaseModel):
    property_id: str
    guest_id: str
    guest_name: str
    room_type_id: str
    check_in_date: date
    check_out_date: date
    adults: int = Field(default=1, gt=0)
    children: int = Field(default=0, ge=0)
    source: BookingSource = BookingSource.DIRECT_SITE
    actor_id: str
    actor_role: Role


class BookingChangeRequest(BaseModel):
    check_in_date: date | None = None
    check_out_date: date | None = None
    adults: int | None = Field(default=None, gt=0)
    children: int | None = Field(default=None, ge=0)
    actor_id: str
    actor_role: Role


class Booking(BaseModel):
    booking_id: str
    property_id: str
    guest_id: str
    guest_name: str
    room_type_id: str
    room_id: str | None = None
    check_in_date: date
    check_out_date: date
    nights: int = Field(gt=0)
    adults: int = Field(gt=0)
    children: int = Field(ge=0)
    source: BookingSource
    status: BookingStatus = BookingStatus.NEW
    price: RateBreakdown
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CheckInRequest(BaseModel):
    booking_id: str
    deposit_amount: float = Field(default=0, ge=0)
    actor_id: str
    actor_role: Role


class CheckOutRequest(BaseModel):
    stay_id: str
    actor_id: str
    actor_role: Role


class FrontdeskStay(BaseModel):
    stay_id: str
    booking_id: str
    guest_id: str
    room_id: str
    check_in_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    check_out_at: datetime | None = None
    deposit_amount: float = Field(default=0, ge=0)
    extras_total: float = Field(default=0, ge=0)
    status: str = "active"


class HousekeepingTaskRequest(BaseModel):
    property_id: str
    room_id: str
    task_type: TaskType
    priority: int = Field(default=3, ge=1, le=5)
    actor_id: str
    actor_role: Role


class HousekeepingTask(BaseModel):
    task_id: str
    property_id: str
    room_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.NEW
    priority: int = Field(default=3, ge=1, le=5)
    assigned_to: str | None = None
    scheduled_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExtraChargeRequest(BaseModel):
    stay_id: str
    service_type: ServiceType
    title: str
    amount: float = Field(gt=0)
    actor_id: str
    actor_role: Role


class ExtraCharge(BaseModel):
    charge_id: str
    stay_id: str
    service_type: ServiceType
    title: str
    amount: float = Field(gt=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChannelSyncEvent(BaseModel):
    event_id: str
    channel: BookingSource
    booking_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CheckInWorkflowResult(BaseModel):
    booking: dict[str, Any]
    assigned_room: dict[str, Any]
    stay: dict[str, Any]
    prep_task: dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
