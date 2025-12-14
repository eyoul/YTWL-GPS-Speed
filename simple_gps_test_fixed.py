#!/usr/bin/env python3
"""
Simple GPS Test Script - No external dependencies
Tests GPS data transmission to listener
"""

import socket
import time
import json
from datetime import datetime

# Configuration
SERVER_IP = "127.0.0.1"
SERVER_PORT = 9000
TEST_IMEI = "862123456789012"
TEST_VEHICLE_ID = None  # Will be set from database (auto-increment)

def send_test_data_csv():
    """Send test GPS data in CSV format"""
    print("Sending CSV test data...")
    
    # Check if we have a valid vehicle_id
    if TEST_VEHICLE_ID is None:
        print("Error: No valid vehicle_id. Please create test vehicle first.")
        return
    
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
            # Send with vehicle_id instead of IMEI
            csv_data = f"{TEST_VEHICLE_ID},{timestamp},{lat},{lon},{speed}\n"
            
            print(f"Sending: {csv_data.strip()}")
            sock.send(csv_data.encode('utf-8'))
            time.sleep(2)  # Wait 2 seconds between points
        
        sock.close()
        print("CSV test data sent successfully!")
        
    except Exception as e:
        print(f"Error sending CSV data: {e}")

def check_api_response():
    """Check if data was received via API"""
    print("Checking API response...")
    
    try:
        import urllib.request
        import urllib.error
        
        url = f"http://{SERVER_IP}:5000/api/latest"
        
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                print(f"API returned {len(data)} records:")
                for record in data[-3:]:  # Show last 3 records
                    print(f"  IMEI: {record['imei']}, Speed: {record['speed']} km/h, "
                          f"Lat: {record['lat']}, Lon: {record['lon']}")
        except urllib.error.URLError as e:
            print(f"API error: {e}")
            
    except ImportError:
        print("urllib not available, skipping API check")
    except Exception as e:
        print(f"Error checking API: {e}")

def create_test_vehicle():
    """Create a test vehicle in the database"""
    global TEST_VEHICLE_ID
    print("Creating test vehicle...")
    
    try:
        import sqlite3
        
        conn = sqlite3.connect('gps.db')
        c = conn.cursor()
        
        # Check if vehicle already exists
        c.execute('SELECT id FROM vehicles WHERE imei = ?', (TEST_IMEI,))
        existing = c.fetchone()
        if existing:
            TEST_VEHICLE_ID = existing[0]
            print(f"Test vehicle already exists with ID: {TEST_VEHICLE_ID}")
            return TEST_VEHICLE_ID
        
        # Create test vehicle
        c.execute('''
            INSERT INTO vehicles (imei, license_plate, make, model, year, vehicle_type, driver_name, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (TEST_IMEI, "AA-00127", "Toyota", "Yaris", 2024, "Speed Limiter", "Test Driver", "Testing"))
        
        conn.commit()
        
        # Get vehicle_id
        c.execute('SELECT id FROM vehicles WHERE imei = ?', (TEST_IMEI,))
        result = c.fetchone()
        if result:
            TEST_VEHICLE_ID = result[0]
            print(f"Test vehicle created successfully with ID: {TEST_VEHICLE_ID}")
        
        conn.close()
        return TEST_VEHICLE_ID
        
    except Exception as e:
        print(f"Error creating vehicle: {e}")
        return None

def main():
    """Run all tests"""
    print("=== Simple GPS Test Suite ===")
    print(f"Testing against: {SERVER_IP}:{SERVER_PORT}")
    print()
    
    # Test 1: Create test vehicle
    create_test_vehicle()
    print()
    
    # Test 2: Send CSV test data
    send_test_data_csv()
    print()
    
    # Test 3: Check API response
    time.sleep(3)  # Wait for data processing
    check_api_response()
    print()
    
    print("=== Test Complete ===")
    print("Check your web dashboard at: http://localhost:5000")
    print("Click 'Live Map' to see the test data on the map!")

if __name__ == "__main__":
    main()
