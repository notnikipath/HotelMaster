# Покрытие требований Task 24

## 1. Поддерживаемые типы объектов

Реализовано в `shared/hotelmaster_common/schemas.py` через `PropertyType`:
- `hotel`
- `hostel`
- `apart_hotel`
- `sanatorium`

## 2. Основные модули

### Модуль номерного фонда
- `room-service`:
- типы номеров и характеристики (`/room-types`)
- статусы (`/rooms/{room_id}/status`)
- тарифы и сезонность (`/rates/quote`)
- автоназначение номера (`/rooms/auto-assign`)

### Модуль бронирования
- `booking-service`:
- прямое бронирование (`POST /bookings` с `source=direct_site`)
- каналы (`source=booking_com|airbnb`, pull-эндпоинты)
- изменение/отмена (`PATCH /bookings/{id}`, `POST /bookings/{id}/cancel`)

### Модуль регистрации
- `frontdesk-service`:
- заселение (`POST /check-in`)
- выписка (`POST /check-out`)
- депозит (поле `deposit_amount`)
- печать документов (`POST /documents/print`)

### Модуль обслуживания
- `housekeeping-service`:
- заявки уборка/ремонт (`POST /tasks`)
- расписание горничных (`GET /maids/schedule`)

### Модуль доп. услуг
- `extra-service`:
- ресторан, spa, трансфер (`/catalog`, `/charges`)
- добавление в счёт (через `frontdesk-service /stays/add-extra`)

### Модуль отчётности
- `reports-service`:
- загрузка, ADR, RevPAR (`/reports/operational`)
- финансы (`/reports/financial`)

## 3. Workflow check-in

`api-gateway /workflow/check-in`:
1. Получение брони
2. Автоназначение номера
3. Резервирование номера
4. Перевод статуса номера в `occupied`
5. Создание проживания (frontdesk)
6. Создание задачи подготовки номера (housekeeping)
7. Уведомление гостя

## 4. Опциональные улучшения

### Группа A
- динамический тариф
- прогноз загрузки + MAPE
- автоназначение номера
- чат-бот

### Группа B
- Booking.com/Airbnb pull
- интеграция с кассой (fiscal receipt endpoint)
- smart-room endpoint
- экспорт в 1С

### Группа C
- кэширование тарифов
- план параллельной обработки
- шардирование по отелю
- асинхронные события каналов

### Группа D
- guest self check-in endpoint
- frontend dashboard (планшетный формат)
- kiosk session API
- voice control API
