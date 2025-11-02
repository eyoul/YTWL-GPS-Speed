Below is the project structure with all code files separated clearly for your YTWL GPS Speed Limiter Flask app.

---

## 📁 Project Structure

```
YTWL_Flask_Tracker/
│
├── listener.py
├── app.py
├── requirements.txt
├── README.md
└── templates/
    └── map.html
```

---

### 🟩 listener.py

```python
import socket
import threading
import sqlite3
import binascii
import struct
from datetime import datetime

DB = 'gps.db'
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 9000

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS raw_packets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT,
        remote_addr TEXT,
        raw_hex TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gps_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        imei TEXT,
        timestamp TEXT,
        latitude REAL,
        longitude REAL,
        speed REAL,
        raw_hex TEXT)''')
    conn.commit()
    conn.close()

def insert_raw(remote, raw_hex):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT INTO raw_packets (received_at, remote_addr, raw_hex) VALUES (?, ?, ?)',
              (datetime.utcnow().isoformat(), remote, raw_hex))
    conn.commit()
    conn.close()

def insert_gps(imei, ts, lat, lon, speed, raw_hex):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT INTO gps_data (imei, timestamp, latitude, longitude, speed, raw_hex) VALUES (?, ?, ?, ?, ?, ?)',
              (imei, ts, lat, lon, speed, raw_hex))
    conn.commit()
    conn.close()

def try_parse_gt06(hex_str):
    try:
        data = binascii.unhexlify(hex_str)
    except Exception:
        return None

    if len(data) < 15 or data[0:2] != b'\x78\x78':
        return None

    try:
        ascii_text = data.decode('latin1', errors='ignore')
        import re
        m = re.search(r"(\d{14,16})", ascii_text)
        imei = m.group(1) if m else None
    except Exception:
        imei = None

    try:
        idx = next((i for i, b in enumerate(data) if b in (0x12, 0x22, 0x10)), None)
        if idx is None:
            return {'imei': imei}
        if len(data) >= idx + 20:
            lat_bytes = data[idx+8:idx+12]
            lon_bytes = data[idx+12:idx+16]
            lat = struct.unpack('>i', lat_bytes)[0] / 30000.0 / 60.0
            lon = struct.unpack('>i', lon_bytes)[0] / 30000.0 / 60.0
            speed = data[idx+16]
            return {'imei': imei, 'latitude': lat, 'longitude': lon, 'speed': speed}
    except Exception:
        pass

    return {'imei': imei}

def handle_client(conn, addr):
    remote = f"{addr[0]}:{addr[1]}"
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            raw_hex = data.hex()
            print(f"[RAW] {remote} -> {raw_hex}")
            insert_raw(remote, raw_hex)
            parsed = try_parse_gt06(raw_hex)
            if parsed and parsed.get('latitude') and parsed.get('longitude'):
                insert_gps(parsed.get('imei') or 'unknown', datetime.utcnow().isoformat(), parsed['latitude'], parsed['longitude'], parsed.get('speed', 0), raw_hex)
            elif parsed and parsed.get('imei'):
                insert_gps(parsed.get('imei'), datetime.utcnow().isoformat(), None, None, None, raw_hex)
    except Exception as e:
        print('Client handler error:', e)
    finally:
        conn.close()

def start_server(host=LISTEN_HOST, port=LISTEN_PORT):
    init_db()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    print(f"Listening on {host}:{port}")
    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print('Server shutting down')
    finally:
        s.close()

if __name__ == '__main__':
    start_server()
```

---

### 🟨 app.py

```python
from flask import Flask, render_template, jsonify
import threading
import sqlite3
from listener import start_server

app = Flask(__name__)
DB = 'gps.db'

def get_latest(limit=100):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT imei, timestamp, latitude, longitude, speed FROM gps_data WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'imei': r[0], 'timestamp': r[1], 'lat': r[2], 'lon': r[3], 'speed': r[4]} for r in rows]

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/api/latest')
def api_latest():
    return jsonify(get_latest(200))

if __name__ == '__main__':
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    app.run(debug=True)
```

---

### 🟦 templates/map.html

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>YTWL GPS Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
  <style> #map { height: 90vh; width: 100%; } </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([9.03, 38.74], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19}).addTo(map);
    let markers = [];

    async function loadPoints(){
      const res = await fetch('/api/latest');
      const points = await res.json();
      markers.forEach(m => map.removeLayer(m));
      markers = [];
      points.forEach(p => {
        const marker = L.marker([p.lat, p.lon]).addTo(map);
        marker.bindPopup(`<b>IMEI:</b> ${p.imei}<br>Speed: ${p.speed} km/h<br>${p.timestamp}`);
        markers.push(marker);
      });
      if(points.length>0) map.setView([points[0].lat, points[0].lon], 13);
    }
    loadPoints();
    setInterval(loadPoints, 5000);
  </script>
</body>
</html>
```

---

### 🧾 requirements.txt

```
Flask>=2.0
pyngrok>=5.0
```

---

### 📘 README.md

````markdown
# YTWL GPS Tracker - Quickstart

### Requirements
- Python 3.8+
- ngrok (or `pyngrok`)
- YTWL GPS device with SIM and power

### Setup
```bash
python -m venv venv
source venv/bin/activate   # or venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
````

### Expose TCP port

```bash
ngrok tcp 9000
```

Send SMS to the device:

```
APN,1,etnet#
SERVER,1,<ngrok_host>,<ngrok_port>#
CHECK#
```

Then
