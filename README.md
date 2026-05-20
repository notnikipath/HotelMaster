# HotelMaster

HotelMaster is a microservice PMS (Property Management System) for hotels, hostels, apart-hotels, and sanatoriums.

## Project Goal

Implement end-to-end hotel operations:
- booking and channel sync,
- check-in and check-out,
- room stock and rates,
- housekeeping and maintenance,
- extra services billing,
- operational and financial reporting.

## Modules

- `api-gateway` - orchestration, auth, unified workflows and dashboard API
- `room-service` - room types, statuses, seasonal and dynamic pricing, auto room assignment
- `booking-service` - direct and OTA bookings, update/cancel, occupancy forecast, async channel events
- `frontdesk-service` - check-in/check-out, deposits, document printing, kiosk/self check-in session
- `housekeeping-service` - cleaning/repair queue, maid schedule, mobile board endpoints
- `extra-service` - restaurant/spa/transfer charges, fiscal receipt, smart-room and voice control endpoints
- `reports-service` - occupancy, ADR, RevPAR, financial reports, forecast accuracy, 1C export endpoint
- `notification-service` - guest notifications and chatbot responses
- `frontend` - React operations dashboard
- `mobile-housekeeping` - React Native prototype for housekeeping staff

## Optional Improvements Implemented

### Group A
- Dynamic pricing based on occupancy and lead time
- Occupancy forecasting + MAPE check endpoint
- Automatic room assignment
- Guest chatbot API

### Group B
- Booking.com and Airbnb pull endpoints
- Fiscal receipt integration endpoint
- Smart-room control endpoint
- 1C export endpoint

### Group C
- Tariff caching (TTL cache)
- Parallel booking processing plan endpoint
- Hotel sharding strategy endpoint
- Async channel update events

### Group D
- Guest self check-in session endpoint
- Dashboard data surface for concierge/tablet-like UI
- Kiosk flow primitive (frontdesk self-check-in)
- Voice room control endpoint

## KPI Targets

- Booking time: `< 3 sec`
- Occupancy forecast quality: `MAPE < 10%`
- Scale target: `up to 5000 rooms`

## Local Run

```bash
cd 'your/project/folder'
docker compose up --build -d
```

## Useful URLs

- Frontend: `http://localhost:5178`
- API Gateway health: `http://localhost:8580/health`
- Services health: `http://localhost:8580/services/health`
- Gateway Swagger: `http://localhost:8580/docs`

## Demo Check-in Workflow

```bash
python scripts/demo_checkin_workflow.py
```

The gateway workflow performs:
1. Load booking
2. Auto-assign room
3. Reserve room and bind to booking
4. Set room status to occupied
5. Create frontdesk stay with deposit
6. Create housekeeping prepare-room task
7. Send guest notification

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Requirements Coverage

Detailed requirement mapping: `docs/requirements_coverage.md`

## Sample Data

```bash
python scripts/generate_sample_data.py
```

Output: `data/samples/hotelmaster_events.json`
