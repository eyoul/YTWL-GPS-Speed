#!/usr/bin/env python3
"""
YTWL GPS Speed Limiter Test Script
Tests device communication and data processing
"""

import socket
import time
import json
import requests
from datetime import datetime

# Configuration
SERVER_IP = "127.0.0.1"  # Change to your AWS IP
SERVER_PORT = 9000
WEB_APP_URL = "http://127.0.0.1:5000"  # Change to your domain

# Test vehicle IMEI (must exist in database)
TEST_IMEI = "862123456789012"

def send_test_data_csv():
    """Send test GPS data in CSV format"""
    print("Sending CSV test data...")
    
    # Create socket connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_IP, SERVER_PORT))
        
        # Test data points around Addis Ababa
        test_points = [
            (9.0331, 38.7500, 0.0),   # Parked
            (9.0341, 38.7510, 25.5), # Moving
            (9.0351, 38.7520, 45.0), # Highway speed
            (9.0361, 38.7530, 65.0), # Over speed limit
            (9.0371, 38.7540, 35.0), # Normal speed
            (9.0381, 38.7550, 0.0),  # Stopped
        ]
        
        for i, (lat, lon, speed) in enumerate(test_points):
            timestamp = datetime.utcnow().isoformat() + "Z"
            csv_data = f"{TEST_IMEI},{timestamp},{lat},{lon},{speed}\n"
            
            print(f"Sending: {csv_data.strip()}")
            sock.send(csv_data.encode('utf-8'))
            time.sleep(2)  # Wait 2 seconds between points
        
        sock.close()
        print("CSV test data sent successfully!")
        
    except Exception as e:
        print(f"Error sending CSV data: {e}")

def send_test_data_binary():
    """Send test GPS data in GT06 binary format"""
    print("Sending binary GT06 test data...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_IP, SERVER_PORT))
        
        # Simple GT06-like binary packet
        # This is a simplified version - real devices use more complex protocols
        test_packet = b'\x78\x78\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        
        sock.send(test_packet)
        sock.close()
        print("Binary test data sent!")
        
    except Exception as e:
        print(f"Error sending binary data: {e}")

def check_api_response():
    """Check if data was received via API"""
    print("Checking API response...")
    
    try:
        response = requests.get(f"{WEB_APP_URL}/api/latest")
        if response.status_code == 200:
            data = response.json()
            print(f"API returned {len(data)} records:")
            for record in data[-3:]:  # Show last 3 records
                print(f"  IMEI: {record['imei']}, Speed: {record['speed']} km/h, "
                      f"Lat: {record['lat']}, Lon: {record['lon']}")
        else:
            print(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"Error checking API: {e}")

def test_vehicle_creation():
    """Test vehicle creation via API"""
    print("Testing vehicle creation...")
    
    try:
        vehicle_data = {
            "imei": TEST_IMEI,
            "license_plate": "YTWL-TEST",
            "make": "YTWL",
            "model": "CA10F",
            "year": 2024,
            "vehicle_type": "Speed Limiter",
            "driver_name": "Test Driver",
            "department": "Testing"
        }
        
        response = requests.post(f"{WEB_APP_URL}/api/vehicles", json=vehicle_data)
        if response.status_code in [200, 201]:
            print("Vehicle created successfully!")
        elif response.status_code == 400 and "already exists" in response.text:
            print("Vehicle already exists (OK)")
        else:
            print(f"Vehicle creation failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error creating vehicle: {e}")

def test_speed_limit():
    """Test speed limit setting"""
    print("Testing speed limit setting...")
    
    try:
        # First get vehicle ID
        vehicles_response = requests.get(f"{WEB_APP_URL}/api/vehicles")
        if vehicles_response.status_code == 200:
            vehicles = vehicles_response.json().get('vehicles', [])
            vehicle_id = None
            
            for vehicle in vehicles:
                if vehicle['imei'] == TEST_IMEI:
                    vehicle_id = vehicle['id']
                    break
            
            if vehicle_id:
                # Set speed limit to 50 km/h
                speed_data = {
                    "vehicle_id": vehicle_id,
                    "speed_limit_kmh": 50.0,
                    "set_by": "Test Script"
                }
                
                response = requests.post(f"{WEB_APP_URL}/api/speed_limits", json=speed_data)
                if response.status_code in [200, 201]:
                    print("Speed limit set successfully!")
                else:
                    print(f"Speed limit setting failed: {response.status_code}")
            else:
                print("Test vehicle not found")
                
    except Exception as e:
        print(f"Error setting speed limit: {e}")

def main():
    """Run all tests"""
    print("=== YTWL GPS Speed Limiter Test Suite ===")
    print(f"Testing against: {SERVER_IP}:{SERVER_PORT}")
    print(f"Web app URL: {WEB_APP_URL}")
    print()
    
    # Test 1: Create test vehicle
    test_vehicle_creation()
    print()
    
    # Test 2: Set speed limit
    test_speed_limit()
    print()
    
    # Test 3: Send CSV test data
    send_test_data_csv()
    print()
    
    # Test 4: Check API response
    time.sleep(3)  # Wait for data processing
    check_api_response()
    print()
    
    # Test 5: Send binary test data (optional)
    # send_test_data_binary()
    
    print("=== Test Complete ===")
    print("Check your web dashboard at:", WEB_APP_URL)
    print("Click 'Live Map' to see the test data on the map!")

if __name__ == "__main__":
    main()
