import socket
import sqlite3
import threading
import datetime
import struct
import binascii

DB = 'gps.db'
HOST = '0.0.0.0'
PORT = 9000  # Make sure this matches your cloudflared tunnel

# Create DB table if not exists
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # GPS data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS gps_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            timestamp TEXT,
            latitude REAL,
            longitude REAL,
            speed REAL
        )
    ''')
    
    # Trips table
    c.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            start_time TEXT,
            end_time TEXT,
            start_lat REAL,
            start_lon REAL,
            end_lat REAL,
            end_lon REAL,
            distance_km REAL,
            avg_speed REAL,
            max_speed REAL,
            duration_minutes INTEGER
        )
    ''')
    
    # Parking/idling events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS parking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            start_time TEXT,
            end_time TEXT,
            latitude REAL,
            longitude REAL,
            duration_minutes INTEGER,
            event_type TEXT CHECK(event_type IN ('parked', 'idling'))
        )
    ''')
    
    # Fuel consumption table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fuel_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            timestamp TEXT,
            fuel_level REAL,
            fuel_filled REAL DEFAULT 0,
            fuel_drained REAL DEFAULT 0,
            event_type TEXT CHECK(event_type IN ('level', 'fill', 'drain'))
        )
    ''')
    
    # Temperature monitoring table
    c.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            timestamp TEXT,
            temperature_celsius REAL,
            sensor_id TEXT
        )
    ''')
    
    # Engine control table
    c.execute('''
        CREATE TABLE IF NOT EXISTS engine_control (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            command TEXT CHECK(command IN ('cut', 'start', 'status')),
            timestamp TEXT,
            status TEXT DEFAULT 'pending',
            response TEXT,
            executed_at TEXT
        )
    ''')
    
    # Speed limits table
    c.execute('''
        CREATE TABLE IF NOT EXISTS speed_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            speed_limit_kmh REAL,
            set_by TEXT,
            set_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Alarm logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            alarm_type TEXT,
            message TEXT,
            timestamp TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT
        )
    ''')
    
    # Trip requests table
    c.execute('''
        CREATE TABLE IF NOT EXISTS trip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            requester_name TEXT,
            request_date TEXT,
            purpose TEXT,
            destination TEXT,
            status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TEXT,
            vehicle_assigned TEXT
        )
    ''')
    
    # Positioning data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS positioning_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            current_latitude REAL,
            current_longitude REAL,
            last_latitude REAL,
            last_longitude REAL,
            timestamp TEXT,
            heading REAL,
            altitude REAL
        )
    ''')
    
    # Vehicles table for CRUD operations
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT UNIQUE NOT NULL,
            license_plate TEXT,
            make TEXT,
            model TEXT,
            year INTEGER,
            color TEXT,
            vehicle_type TEXT,
            driver_name TEXT,
            driver_contact TEXT,
            department TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'maintenance', 'retired')),
            fuel_capacity REAL,
            current_fuel REAL DEFAULT 0,
            mileage REAL DEFAULT 0,
            last_service_date TEXT,
            next_service_date TEXT,
            insurance_expiry TEXT,
            registration_expiry TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_point(imei, ts_iso, lat, lon, speed):
    conn_db = sqlite3.connect(DB)
    c = conn_db.cursor()
    c.execute('''
        INSERT INTO gps_data (imei, timestamp, latitude, longitude, speed)
        VALUES (?, ?, ?, ?, ?)
    ''', (imei, ts_iso, lat, lon, speed))
    conn_db.commit()
    conn_db.close()
    
    # Also update positioning data
    update_positioning_data(imei, lat, lon, ts_iso)

def update_positioning_data(imei, lat, lon, timestamp):
    conn_db = sqlite3.connect(DB)
    c = conn_db.cursor()
    
    # Get last known position
    c.execute('''
        SELECT current_latitude, current_longitude FROM positioning_data 
        WHERE imei = ? ORDER BY timestamp DESC LIMIT 1
    ''', (imei,))
    last_pos = c.fetchone()
    
    if last_pos:
        last_lat, last_lon = last_pos
    else:
        last_lat, last_lon = lat, lon
    
    # Insert new positioning data
    c.execute('''
        INSERT INTO positioning_data 
        (imei, current_latitude, current_longitude, last_latitude, last_longitude, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (imei, lat, lon, last_lat, last_lon, timestamp))
    
    conn_db.commit()
    conn_db.close()

def _parse_bcd_datetime(b: bytes) -> datetime.datetime:
    # YY MM DD HH mm ss, BCD-like but many devices send raw numbers already 0-99
    if len(b) < 6:
        return datetime.datetime.utcnow()
    try:
        yy, mo, dd, hh, mm, ss = b[:6]
        year = 2000 + (yy % 100)
        return datetime.datetime(year, max(1, mo), max(1, dd), min(hh, 23), min(mm, 59), min(ss, 59))
    except Exception:
        return datetime.datetime.utcnow()

def try_decode_gt06(frame: bytes):
    # Basic validation
    if len(frame) < 12:
        return None
    if frame[:2] not in (b'\x78\x78', b'\x79\x79'):
        return None
    length = frame[2]
    if len(frame) < length + 5:
        return None
    proto = frame[3]
    if proto not in (0x10, 0x12, 0x22):  # common location protocols
        return None

    # Heuristic search: find datetime (6 bytes) then lat/lon (4 bytes BE each), speed (1)
    # Try offsets 4..10 for datetime start, and small deltas for sat byte.
    for dt_off in (4, 5, 6, 7, 8, 9, 10):
        if dt_off + 6 + 1 + 4 + 4 + 1 > len(frame):
            continue
        ts = _parse_bcd_datetime(frame[dt_off:dt_off+6])
        for delta in (1, 2, 3):
            idx = dt_off + 6 + delta
            if idx + 9 > len(frame):
                continue
            lat_raw = struct.unpack('>I', frame[idx:idx+4])[0]
            lon_raw = struct.unpack('>I', frame[idx+4:idx+8])[0]
            spd = frame[idx+8]
            # Two common scalings
            candidates = [
                (lat_raw / 1800000.0, lon_raw / 1800000.0),
                (lat_raw / 30000.0 / 60.0, lon_raw / 30000.0 / 60.0),
            ]
            for lat_val, lon_val in candidates:
                if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                    return {
                        'imei': 'UNKNOWN',
                        'timestamp': ts.isoformat(),
                        'lat': float(lat_val),
                        'lon': float(lon_val),
                        'speed': float(spd),
                    }
    return None

def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr}")
    buffer = b''
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                # Log hex for visibility
                print(f"[HEX] {data.hex()}")

                # CSV fallback path (if device sends text lines)
                try:
                    text = data.decode('utf-8').strip()
                    if ',' in text:
                        parts = text.split(',')
                        if len(parts) >= 5:
                            imei = parts[0]
                            timestamp = parts[1]
                            lat = float(parts[2])
                            lon = float(parts[3])
                            speed = float(parts[4])
                            save_point(imei, timestamp, lat, lon, speed)
                except UnicodeDecodeError:
                    pass

                # Binary GT06-like parsing using a buffer
                buffer += data
                while True:
                    if len(buffer) < 5:
                        break
                    if buffer[:2] not in (b'\x78\x78', b'\x79\x79'):
                        # drop until possible header
                        buffer = buffer[1:]
                        continue
                    length = buffer[2]
                    total = length + 5
                    if len(buffer) < total:
                        break
                    frame = buffer[:total]
                    buffer = buffer[total:]

                    decoded = try_decode_gt06(frame)
                    if decoded and decoded.get('lat') is not None and decoded.get('lon') is not None:
                        save_point(
                            decoded.get('imei', 'UNKNOWN'),
                            decoded.get('timestamp', datetime.datetime.utcnow().isoformat()),
                            decoded['lat'], decoded['lon'], decoded.get('speed', 0.0)
                        )
            except Exception as e:
                print(f"[ERROR] {e}")
                break

def start_server():
    init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[LISTENING] TCP server on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()
