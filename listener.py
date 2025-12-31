# listener.py
import socket
import threading
import sqlite3
import datetime

HOST = '0.0.0.0'
PORT = 9000
DB = '/var/www/YTWL-GPS-Speed/gps.db'

from redis_queue import push_packet
import datetime

def handle_packet(imei, lat, lon, speed, heading):
    packet = {
        "imei": imei,
        "lat": lat,
        "lon": lon,
        "speed": speed,
        "heading": heading,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    push_packet(packet)

def save_gps(imei, lat, lon, speed):
    conn = sqlite3.connect(DB, timeout=30)
    c = conn.cursor()
    c.execute("""
        INSERT INTO gps_data (vehicle_id, timestamp, latitude, longitude, speed)
        SELECT id, ?, ?, ?, ?
        FROM vehicles WHERE imei = ?
    """, (
        datetime.datetime.utcnow().isoformat(),
        lat, lon, speed, imei
    ))
    conn.commit()
    conn.close()

def handle_client(conn, addr):
    try:
        data = conn.recv(1024).decode(errors='ignore')
        print("RAW:", data)

        # TODO: parse YTWL protocol here
        imei = "123456789012345"
        lat = 9.03
        lon = 38.74
        speed = 40

        save_gps(imei, lat, lon, speed)
    except Exception as e:
        print("ERR:", e)
    finally:
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(100)
    print(f"GPS Listener on {PORT}")

    while True:
        conn, addr = s.accept()
        threading.Thread(
            target=handle_client,
            args=(conn, addr),
            daemon=True
        ).start()

if __name__ == "__main__":
    start_server()
