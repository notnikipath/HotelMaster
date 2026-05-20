from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8580"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    result = request(
        "POST",
        "/workflow/check-in",
        {
            "booking_id": "BK-DEMO",
            "deposit_amount": 5000,
            "preferred_floor": 2,
            "actor_id": "FD-001",
            "actor_role": "admin",
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
