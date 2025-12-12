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
            vehicle_id INTEGER,
            timestamp TEXT,
            latitude REAL,
            longitude REAL,
            speed REAL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Trips table
    c.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            start_lat REAL,
            start_lon REAL,
            end_lat REAL,
            end_lon REAL,
            distance_km REAL,
            avg_speed REAL,
            max_speed REAL,
            duration_minutes INTEGER,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Parking/idling events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS parking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            latitude REAL,
            longitude REAL,
            duration_minutes INTEGER,
            event_type TEXT CHECK(event_type IN ('parked', 'idling')),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Fuel consumption table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fuel_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            timestamp TEXT,
            fuel_level REAL,
            fuel_filled REAL DEFAULT 0,
            fuel_drained REAL DEFAULT 0,
            event_type TEXT CHECK(event_type IN ('level', 'fill', 'drain')),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Temperature monitoring table
    c.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            timestamp TEXT,
            temperature_celsius REAL,
            sensor_id TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Engine control table
    c.execute('''
        CREATE TABLE IF NOT EXISTS engine_control (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            command TEXT CHECK(command IN ('cut', 'start', 'status')),
            timestamp TEXT,
            status TEXT DEFAULT 'pending',
            response TEXT,
            executed_at TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')
    
    # Speed limits table
    c.execute('''
        CREATE TABLE IF NOT EXISTS speed_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            speed_limit_kmh REAL,
            set_by TEXT,
            set_at TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')
    
    # Alarm logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            alarm_type TEXT,
            message TEXT,
            timestamp TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')
    
    # Trip requests table
    c.execute('''
        CREATE TABLE IF NOT EXISTS trip_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            department TEXT,
            requester_name TEXT,
            request_date TEXT,
            purpose TEXT,
            destination TEXT,
            status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TEXT,
            vehicle_assigned TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')
    
    # Positioning data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS positioning_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER,
            current_latitude REAL,
            current_longitude REAL,
            last_latitude REAL,
            last_longitude REAL,
            timestamp TEXT,
            heading REAL,
            altitude REAL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
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

def migrate_vehicle_ids():
    """Migrate existing data to populate vehicle_id columns based on IMEI"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # First, populate vehicle_id columns from IMEI for tables that still have both
    tables_to_migrate = []
    
    # Check which tables still have IMEI columns
    for table, vehicle_id_col, imei_col in [
        ('trips', 'vehicle_id', 'imei'),
        ('parking_events', 'vehicle_id', 'imei'),
        ('fuel_data', 'vehicle_id', 'imei'),
        ('temperature_data', 'vehicle_id', 'imei'),
        ('trip_requests', 'vehicle_id', 'imei')
    ]:
        try:
            c.execute(f'PRAGMA table_info({table})')
            columns = [col[1] for col in c.fetchall()]
            if imei_col in columns and vehicle_id_col in columns:
                tables_to_migrate.append((table, vehicle_id_col, imei_col))
        except sqlite3.OperationalError:
            continue
    
    # Update vehicle_id based on IMEI for tables that have both columns
    for table, vehicle_id_col, imei_col in tables_to_migrate:
        c.execute(f'''
            UPDATE {table}
            SET {vehicle_id_col} = (
                SELECT id FROM vehicles WHERE vehicles.imei = {table}.{imei_col}
            )
            WHERE {vehicle_id_col} IS NULL AND {imei_col} IS NOT NULL
        ''')
        print(f"Migrated {table}")
    
    # Then remove IMEI columns from tables that no longer need them
    tables_to_remove_imei = ['trips', 'parking_events', 'fuel_data', 'temperature_data']
    
    for table in tables_to_remove_imei:
        try:
            c.execute(f'PRAGMA table_info({table})')
            columns = [col[1] for col in c.fetchall()]
            if 'imei' in columns:
                c.execute(f'ALTER TABLE {table} DROP COLUMN imei')
                print(f"Dropped IMEI column from {table}")
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            # Column might not exist or already dropped
            print(f"Could not drop IMEI from {table}: {e}")
    
    conn.commit()
    conn.close()
    print("Vehicle ID migration and IMEI column cleanup completed")

def save_trip(vehicle_id, start_time, end_time, start_lat, start_lon, end_lat, end_lon, distance_km, avg_speed, max_speed, duration_minutes):
    """Save trip data with normalized vehicle_id"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO trips (vehicle_id, start_time, end_time, start_lat, start_lon, end_lat, end_lon, distance_km, avg_speed, max_speed, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, start_time, end_time, start_lat, start_lon, end_lat, end_lon, distance_km, avg_speed, max_speed, duration_minutes))
    conn.commit()
    conn.close()

def save_parking_event(vehicle_id, start_time, end_time, latitude, longitude, duration_minutes, event_type):
    """Save parking event with normalized vehicle_id"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO parking_events (vehicle_id, start_time, end_time, latitude, longitude, duration_minutes, event_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, start_time, end_time, latitude, longitude, duration_minutes, event_type))
    conn.commit()
    conn.close()

def save_fuel_data(vehicle_id, timestamp, fuel_level, fuel_filled=0, fuel_drained=0, event_type='level'):
    """Save fuel data with normalized vehicle_id"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO fuel_data (vehicle_id, timestamp, fuel_level, fuel_filled, fuel_drained, event_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, timestamp, fuel_level, fuel_filled, fuel_drained, event_type))
    conn.commit()
    conn.close()

def save_temperature_data(vehicle_id, timestamp, temperature_celsius, sensor_id=None):
    """Save temperature data with normalized vehicle_id"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO temperature_data (vehicle_id, timestamp, temperature_celsius, sensor_id)
        VALUES (?, ?, ?, ?)
    ''', (vehicle_id, timestamp, temperature_celsius, sensor_id))
    conn.commit()
    conn.close()

def save_trip_request(vehicle_id, department, requester_name, request_date, purpose, destination, status='pending', approved_by=None, approved_at=None, vehicle_assigned=None):
    """Save trip request with normalized vehicle_id"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO trip_requests (vehicle_id, department, requester_name, request_date, purpose, destination, status, approved_by, approved_at, vehicle_assigned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, department, requester_name, request_date, purpose, destination, status, approved_by, approved_at, vehicle_assigned))
    conn.commit()
    conn.close()

def get_vehicle_id_from_imei(imei):
    """Get vehicle_id from IMEI, return None if not found"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('SELECT id FROM vehicles WHERE imei = ?', (imei,))
    result = c.fetchone()
    conn.close()
    
    return result[0] if result else None

def save_point(vehicle_id, ts_iso, lat, lon, speed):
    conn_db = sqlite3.connect(DB)
    c = conn_db.cursor()
    c.execute('''
        INSERT INTO gps_data (vehicle_id, timestamp, latitude, longitude, speed)
        VALUES (?, ?, ?, ?, ?)
    ''', (vehicle_id, ts_iso, lat, lon, speed))
    conn_db.commit()
    conn_db.close()
    
    # Also update positioning data
    update_positioning_data(vehicle_id, lat, lon)

def update_positioning_data(vehicle_id, latitude, longitude, heading=None, altitude=None):
    """Update positioning data for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Update or insert positioning data
    c.execute('''
        INSERT OR REPLACE INTO positioning_data 
        (vehicle_id, current_latitude, current_longitude, last_latitude, last_longitude, timestamp, heading, altitude)
        VALUES (?, ?, ?, 
                (SELECT current_latitude FROM positioning_data WHERE vehicle_id = ?),
                (SELECT current_longitude FROM positioning_data WHERE vehicle_id = ?),
                ?, ?, ?)
    ''', (vehicle_id, latitude, longitude, vehicle_id, vehicle_id, datetime.datetime.utcnow().isoformat(), heading, altitude))
    
    conn.commit()
    conn.close()

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
                            identifier = parts[0]
                            timestamp = parts[1]
                            lat = float(parts[2])
                            lon = float(parts[3])
                            speed = float(parts[4])
                            
                            # Check if identifier is numeric (vehicle_id) or IMEI
                            try:
                                vehicle_id = int(identifier)
                                # Direct vehicle_id provided
                                if vehicle_id > 0:
                                    save_point(vehicle_id, timestamp, lat, lon, speed)
                                else:
                                    print(f"[WARNING] Invalid vehicle_id: {vehicle_id}")
                            except ValueError:
                                # IMEI provided, get vehicle_id from IMEI
                                imei = identifier
                                vehicle_id = get_vehicle_id_from_imei(imei)
                                if vehicle_id:
                                    save_point(vehicle_id, timestamp, lat, lon, speed)
                                else:
                                    print(f"[WARNING] Vehicle not found for IMEI: {imei}")
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
                        imei = decoded.get('imei', 'UNKNOWN')
                        # Get vehicle_id from IMEI
                        vehicle_id = get_vehicle_id_from_imei(imei) if imei != 'UNKNOWN' else None
                        if vehicle_id:
                            save_point(
                                vehicle_id,
                                decoded.get('timestamp', datetime.datetime.utcnow().isoformat()),
                                decoded['lat'], decoded['lon'], decoded.get('speed', 0.0)
                            )
                        else:
                            print(f"[WARNING] Vehicle not found for IMEI: {imei}")
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
