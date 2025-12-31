# CBE GPS Tracker

A lightweight GPS vehicle tracking web app built with Flask and Socket.IO. It listens for GT06-compatible GPS device packets over TCP, stores positions in SQLite, and provides a real-time map and fleet management UI.

## Features

- Real-time position updates via WebSockets
- Auto-registration of new devices on first packet
- Vehicle list with online/offline status and last seen
- Vehicle profiles (name, registration, driver)
- Track live on map with Leaflet
- Route history replay
- Basic geofencing with alerts

## Tech Stack

- Flask + Flask-SocketIO (eventlet)
- SQLite (file: `fleet.db`)
- Leaflet, Bootstrap 5

## Getting Started

### Prerequisites

- Python 3.11+

### Local Run

1. Create a virtual environment and install deps:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Run the server:

   ```bash
   set SECRET_KEY=change-me
   python app.py
   ```

3. Open http://localhost:5000

4. Configure your GPS device to send GT06 packets to your server IP on TCP port 6013.

### Docker

Build and run:

```bash
docker build -t cbe-gps-tracker .
docker run -p 5000:5000 -p 6013:6013 -e SECRET_KEY=change-me cbe-gps-tracker
```

Open http://localhost:5000

## Configuration

- `SECRET_KEY`: Flask secret for sessions and Socket.IO (environment variable)

## Notes

- Timestamps are stored as ISO 8601 strings for simple ordering.
- The app creates indexes on `positions(imei, timestamp)` for speed.

## Roadmap

- Authentication and roles
- REST API tokens
- Better GT06 decoding coverage and ACKs
- Pagination and map clustering
- Export reports (CSV/Excel)

STEP 1: FIX ARCHITECTURE (VERY IMPORTANT)

Right now you are doing this:

Gunicorn (web)

TCP GPS listener

SQLite writes
➡️ ALL inside one process

GPS Devices
   |
   | TCP :9000
   v
GPS Listener (systemd)
   |
   | Queue
   v
Redis (Buffer)
   |
   | Worker
   v
PostgreSQL
   |
   | API
   v
Flask + Gunicorn
   |
   | WebSocket
   v
Live Map (Leaflet)

PHASES (WE DO IN ORDER)
✅ Phase 1 — PostgreSQL Migration (MOST IMPORTANT)

SQLite ❌
PostgreSQL ✅

✅ Phase 2 — Redis Queue (No Data Loss)

Listener NEVER touches DB directly

Redis buffers packets

✅ Phase 3 — WebSocket Live Tracking

Map updates instantly

No polling every 5 seconds

✅ Phase 4 — Device Commands

Engine Cut

Engine Resume

Speed Limit Push

✅ Phase 5 — Security & Scale

Auth

HTTPS

Load testing


GPS Device
   ↓ TCP
Listener
   ↓
Redis Queue
   ↓
Worker
   ↓
PostgreSQL
   ↓
WebSocket Broadcast
   ↓
Browser Map (Instant update)
