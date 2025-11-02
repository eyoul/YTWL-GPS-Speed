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
