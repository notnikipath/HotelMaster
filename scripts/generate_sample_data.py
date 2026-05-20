from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROPERTY_TYPES = ["hotel", "hostel", "apart_hotel", "sanatorium"]
SOURCES = ["direct_site", "booking_com", "airbnb", "walk_in"]
SERVICES = ["restaurant", "spa", "transfer", "laundry"]
CITIES = ["Moscow", "Saint Petersburg", "Kazan", "Sochi", "Novosibirsk"]


def generate_record(index: int) -> dict:
    check_in = datetime.now(UTC).date() + timedelta(days=random.randint(1, 120))
    nights = random.randint(1, 10)
    return {
        "booking_id": f"BK-{index:06d}",
        "property_id": f"PROP-{random.randint(1, 40):03d}",
        "property_type": random.choice(PROPERTY_TYPES),
        "city": random.choice(CITIES),
        "source": random.choice(SOURCES),
        "check_in_date": check_in.isoformat(),
        "check_out_date": (check_in + timedelta(days=nights)).isoformat(),
        "nights": nights,
        "occupancy_ratio": round(random.uniform(0.35, 0.98), 3),
        "nightly_rate": round(random.uniform(2200, 14500), 2),
        "total_amount": 0,
        "extra_service": random.choice(SERVICES),
        "extra_amount": round(random.uniform(300, 6500), 2),
        "created_at": (datetime.now(UTC) - timedelta(minutes=index)).isoformat(),
    }


if __name__ == "__main__":
    random.seed(42)
    output = Path(__file__).resolve().parents[1] / "data" / "samples" / "hotelmaster_events.json"
    payload = []
    for index in range(1, 15001):
        item = generate_record(index)
        item["total_amount"] = round(item["nightly_rate"] * item["nights"] + item["extra_amount"], 2)
        payload.append(item)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} records to {output}")
