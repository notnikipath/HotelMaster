from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

room_module = load_module("room_module", ROOT / "room-service" / "app" / "main.py")
booking_module = load_module("booking_module", ROOT / "booking-service" / "app" / "main.py")
frontdesk_module = load_module("frontdesk_module", ROOT / "frontdesk-service" / "app" / "main.py")
housekeeping_module = load_module("housekeeping_module", ROOT / "housekeeping-service" / "app" / "main.py")
extra_module = load_module("extra_module", ROOT / "extra-service" / "app" / "main.py")
reports_module = load_module("reports_module", ROOT / "reports-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")

room_client = TestClient(room_module.app)
booking_client = TestClient(booking_module.app)
frontdesk_client = TestClient(frontdesk_module.app)
housekeeping_client = TestClient(housekeeping_module.app)
extra_client = TestClient(extra_module.app)
reports_client = TestClient(reports_module.app)
notification_client = TestClient(notification_module.app)


def test_booking_room_assignment_flow() -> None:
    booking_resp = booking_client.post(
        "/bookings",
        json={
            "property_id": "PROP-001",
            "guest_id": "GUEST-T1",
            "guest_name": "Test Guest",
            "room_type_id": "RT-STD",
            "check_in_date": "2026-06-14",
            "check_out_date": "2026-06-17",
            "adults": 2,
            "children": 0,
            "source": "direct_site",
            "actor_id": "MGR-1",
            "actor_role": "manager",
        },
    )
    assert booking_resp.status_code == 200
    booking = booking_resp.json()

    room_resp = room_client.post(
        "/rooms/auto-assign",
        json={
            "property_id": "PROP-001",
            "room_type_id": "RT-STD",
            "check_in_date": booking["check_in_date"],
            "check_out_date": booking["check_out_date"],
        },
    )
    assert room_resp.status_code == 200
    room = room_resp.json()

    reserve_resp = room_client.post(
        "/rooms/reserve",
        json={
            "booking_id": booking["booking_id"],
            "room_id": room["room_id"],
            "check_in_date": booking["check_in_date"],
            "check_out_date": booking["check_out_date"],
            "actor_id": "MGR-1",
            "actor_role": "manager",
        },
    )
    assert reserve_resp.status_code == 200

    assign_resp = booking_client.post(
        f"/bookings/{booking['booking_id']}/assign-room",
        json={"room_id": room["room_id"], "actor_id": "MGR-1", "actor_role": "manager"},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["room_id"] == room["room_id"]


def test_frontdesk_housekeeping_extra_reports_flow() -> None:
    stay_resp = frontdesk_client.post(
        "/check-in",
        json={
            "booking_id": "BK-DEMO",
            "guest_id": "GUEST-001",
            "room_id": "RM-0101",
            "deposit_amount": 6000,
            "actor_id": "FD-001",
            "actor_role": "receptionist",
        },
    )
    assert stay_resp.status_code == 200
    stay = stay_resp.json()

    hk_resp = housekeeping_client.post(
        "/tasks",
        json={
            "property_id": "PROP-001",
            "room_id": "RM-0101",
            "task_type": "cleaning",
            "priority": 2,
            "actor_id": "MGR-1",
            "actor_role": "manager",
        },
    )
    assert hk_resp.status_code == 200

    charge_resp = extra_client.post(
        "/charges",
        json={
            "stay_id": stay["stay_id"],
            "service_type": "restaurant",
            "title": "Dinner",
            "amount": 2500,
            "actor_id": "ACC-1",
            "actor_role": "accountant",
        },
    )
    assert charge_resp.status_code == 200

    add_extra_resp = frontdesk_client.post(
        "/stays/add-extra",
        json={
            "stay_id": stay["stay_id"],
            "amount": charge_resp.json()["amount"],
            "actor_id": "ACC-1",
            "actor_role": "accountant",
        },
    )
    assert add_extra_resp.status_code == 200

    checkout_resp = frontdesk_client.post(
        "/check-out",
        json={"stay_id": stay["stay_id"], "actor_id": "FD-001", "actor_role": "receptionist"},
    )
    assert checkout_resp.status_code == 200
    assert checkout_resp.json()["stay"]["status"] == "closed"

    report_resp = reports_client.get(
        "/reports/operational",
        params={"property_id": "PROP-001", "actor_role": "manager"},
    )
    assert report_resp.status_code == 200
    assert "revpar" in report_resp.json()

    notice_resp = notification_client.post(
        "/notify/send",
        json={
            "channel": "email",
            "recipient": "guest@example.com",
            "subject": "Thanks for your stay",
            "body": "Come back soon",
            "actor_role": "admin",
        },
    )
    assert notice_resp.status_code == 200
