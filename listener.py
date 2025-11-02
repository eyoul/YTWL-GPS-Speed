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
