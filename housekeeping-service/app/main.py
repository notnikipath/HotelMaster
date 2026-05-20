from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.hotelmaster_common import (
    HousekeepingTask,
    HousekeepingTaskRequest,
    Role,
    Settings,
    TaskStatus,
    TaskType,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="housekeeping-service", service_port=8504)
app = FastAPI(title="HotelMaster Housekeeping Service", version="1.0.0")


class TaskAssignRequest(BaseModel):
    maid_id: str
    scheduled_at: datetime
    actor_id: str
    actor_role: Role


class TaskStatusRequest(BaseModel):
    status: TaskStatus
    actor_id: str
    actor_role: Role


class PrepareRoomRequest(BaseModel):
    property_id: str
    room_id: str


TaskAssignRequest.model_rebuild()
TaskStatusRequest.model_rebuild()
PrepareRoomRequest.model_rebuild()


tasks: dict[str, HousekeepingTask] = {
    "HK-DEMO": HousekeepingTask(
        task_id="HK-DEMO",
        property_id="PROP-001",
        room_id="RM-0101",
        task_type=TaskType.CLEANING,
        status=TaskStatus.NEW,
        priority=2,
        assigned_to="MAID-01",
        scheduled_at=datetime.now(UTC),
    )
}

audit_log: list[dict[str, Any]] = []
maid_shift_templates = {
    "MAID-01": {"name": "Anna", "from": "08:00", "to": "17:00"},
    "MAID-02": {"name": "Maria", "from": "09:00", "to": "18:00"},
    "MAID-03": {"name": "Elena", "from": "10:00", "to": "19:00"},
}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="housekeeping",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/tasks")
async def create_task(request: HousekeepingTaskRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "housekeeping:manage")
    task = HousekeepingTask(
        task_id=str(uuid4()),
        property_id=request.property_id,
        room_id=request.room_id,
        task_type=request.task_type,
        priority=request.priority,
        status=TaskStatus.NEW,
    )
    tasks[task.task_id] = task
    _audit(request.actor_id, request.actor_role, "housekeeping.task.create", task.task_id)
    return task.model_dump(mode="json")


@app.get("/tasks")
async def list_tasks(
    property_id: str | None = None,
    room_id: str | None = None,
    status: TaskStatus | None = None,
    task_type: TaskType | None = None,
) -> dict[str, Any]:
    items = []
    for task in tasks.values():
        if property_id and task.property_id != property_id:
            continue
        if room_id and task.room_id != room_id:
            continue
        if status and task.status != status:
            continue
        if task_type and task.task_type != task_type:
            continue
        items.append(task.model_dump(mode="json"))
    items.sort(key=lambda item: (item["priority"], item["created_at"]))
    return {"items": items, "count": len(items)}


@app.post("/tasks/{task_id}/assign")
async def assign_task(task_id: str, request: TaskAssignRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "housekeeping:manage")
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.assigned_to = request.maid_id
    task.scheduled_at = request.scheduled_at
    _audit(request.actor_id, request.actor_role, "housekeeping.task.assign", task_id, {"maid_id": request.maid_id})
    return task.model_dump(mode="json")


@app.post("/tasks/{task_id}/status")
async def update_task_status(task_id: str, request: TaskStatusRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "housekeeping:update")
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = request.status
    _audit(request.actor_id, request.actor_role, "housekeeping.task.status", task_id, {"status": request.status.value})
    return task.model_dump(mode="json")


@app.post("/prepare-room")
async def prepare_room(request: PrepareRoomRequest) -> dict[str, Any]:
    task = HousekeepingTask(
        task_id=str(uuid4()),
        property_id=request.property_id,
        room_id=request.room_id,
        task_type=TaskType.PREPARE_ROOM,
        priority=1,
        status=TaskStatus.NEW,
    )
    tasks[task.task_id] = task
    return task.model_dump(mode="json")


@app.get("/maids/schedule")
async def maids_schedule(target_date: date | None = None) -> dict[str, Any]:
    day = target_date or datetime.now(UTC).date()
    schedule = []
    for maid_id, profile in maid_shift_templates.items():
        start = datetime.combine(day, time.fromisoformat(profile["from"]), tzinfo=UTC)
        finish = datetime.combine(day, time.fromisoformat(profile["to"]), tzinfo=UTC)
        load = len(
            [
                task
                for task in tasks.values()
                if task.assigned_to == maid_id
                and task.scheduled_at is not None
                and task.scheduled_at.date() == day
            ]
        )
        schedule.append(
            {
                "maid_id": maid_id,
                "name": profile["name"],
                "shift_start": start.isoformat(),
                "shift_end": finish.isoformat(),
                "assigned_tasks": load,
            }
        )
    return {"date": day.isoformat(), "items": schedule, "count": len(schedule)}


@app.get("/mobile/board")
async def mobile_board(maid_id: str) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    items = [
        task.model_dump(mode="json")
        for task in tasks.values()
        if task.assigned_to == maid_id
        and (task.scheduled_at is None or task.scheduled_at.date() == today)
    ]
    return {"maid_id": maid_id, "items": items, "count": len(items)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
