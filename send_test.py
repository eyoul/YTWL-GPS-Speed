import socket
import time

HOST = '127.0.0.1'  # TCP listener address
PORT = 9000         # TCP listener port

# GPS message using vehicle_id: VEHICLE_ID,TIMESTAMP,LAT,LON,SPEED
# Vehicle ID 1 corresponds to IMEI 123456789012345
message = "1,2025-11-02 17:50:09,9.03,38.74,3\n"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(message.encode())
    print("Message sent!")
