import socket
import time

HOST = '127.0.0.1'  # TCP listener address
PORT = 9000         # TCP listener port

# Example GPS message: IMEI,TIMESTAMP,LAT,LON,SPEED
message = "123456789012345,2025-11-02 17:50:09,9.03,38.74,50\n"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(message.encode())
    print("Message sent!")
