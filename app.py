from flask import Flask, render_template, jsonify, request
import threading
from listener import start_server
from enhanced_alarm import add_alarm_routes, enhanced_log_alarm
import sqlite3
import datetime
import math

app = Flask(__name__)
DB = 'gps.db'

def save_gps(imei, timestamp, lat, lon, speed):
    # Get vehicle_id from IMEI
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        print(f"Warning: Vehicle not found for IMEI {imei}")
        return
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO gps_data (vehicle_id, timestamp, latitude, longitude, speed)
        VALUES (?, ?, ?, ?, ?)
    ''', (vehicle_id, timestamp, lat, lon, speed))
    conn.commit()
    conn.close()
    
def get_latest(limit=100):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        SELECT v.imei, v.license_plate, g.timestamp, g.latitude, g.longitude, g.speed 
        FROM gps_data g
        JOIN vehicles v ON g.vehicle_id = v.id
        WHERE g.latitude IS NOT NULL AND g.longitude IS NOT NULL 
        ORDER BY g.id DESC 
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'imei': r[0], 'license_plate': r[1], 'timestamp': r[2], 'lat': r[3], 'lon': r[4], 'speed': r[5]} for r in rows]

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def detect_parking_events(imei, start_date=None, end_date=None):
    # Get vehicle_id for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return []
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT g.timestamp, g.latitude, g.longitude, g.speed 
        FROM gps_data g
        JOIN vehicles v ON g.vehicle_id = v.id
        WHERE v.imei = ? AND g.latitude IS NOT NULL AND g.longitude IS NOT NULL
    '''
    params = [imei]
    
    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)
    
    query += ' ORDER BY timestamp'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    parking_events = []
    if not rows:
        return parking_events
    
    i = 0
    while i < len(rows):
        timestamp, lat, lon, speed = rows[i]
        
        # Check if vehicle is stopped (speed < 1 km/h)
        if speed < 1.0:
            start_time = timestamp
            start_lat = lat
            start_lon = lon
            
            # Find when vehicle starts moving again
            j = i + 1
            while j < len(rows) and rows[j][3] < 1.0:
                j += 1
            
            if j < len(rows):
                end_time = rows[j][0]
            else:
                end_time = rows[-1][0]
            
            # Calculate duration
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
            
            # Determine if idling (engine on) or parked (engine off)
            event_type = 'idling' if duration_minutes < 30 else 'parked'
            
            if duration_minutes >= 5:  # Only record events longer than 5 minutes
                parking_events.append({
                    'vehicle_id': vehicle_id,
                    'imei': imei,
                    'start_time': start_time,
                    'end_time': end_time,
                    'latitude': start_lat,
                    'longitude': start_lon,
                    'duration_minutes': duration_minutes,
                    'event_type': event_type
                })
            
            i = j
        else:
            i += 1
    
    return parking_events

def get_daily_mileage(imei, start_date=None, end_date=None):
    # Get vehicle_id for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return []
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT DATE(g.timestamp) as date, g.latitude, g.longitude, g.speed
        FROM gps_data g
        JOIN vehicles v ON g.vehicle_id = v.id
        WHERE v.imei = ? AND g.latitude IS NOT NULL AND g.longitude IS NOT NULL
    '''
    params = [imei]
    
    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)
    
    query += ' ORDER BY timestamp'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    daily_mileage = {}
    current_date = None
    last_pos = None
    
    for row in rows:
        date, lat, lon, speed = row
        
        if date not in daily_mileage:
            daily_mileage[date] = 0.0
        
        if last_pos and date == current_date:
            last_lat, last_lon = last_pos
            distance = calculate_distance(last_lat, last_lon, lat, lon)
            if speed > 1.0:  # Only count distance when vehicle is moving
                daily_mileage[date] += distance
        
        current_date = date
        last_pos = (lat, lon)
    
    return [{'vehicle_id': vehicle_id, 'imei': imei, 'date': date, 'miles': round(km * 0.621371, 2)} for date, km in daily_mileage.items()]

def get_trip_summary(imei, start_date=None, end_date=None):
    # Get vehicle_id for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return []
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT g.timestamp, g.latitude, g.longitude, g.speed
        FROM gps_data g
        JOIN vehicles v ON g.vehicle_id = v.id
        WHERE v.imei = ? AND g.latitude IS NOT NULL AND g.longitude IS NOT NULL
    '''
    params = [imei]
    
    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)
    
    query += ' ORDER BY timestamp'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    trips = []
    if not rows:
        return trips
    
    i = 0
    while i < len(rows):
        timestamp, lat, lon, speed = rows[i]
        
        # Start of a trip (vehicle starts moving)
        if speed > 1.0:
            start_time = timestamp
            start_lat = lat
            start_lon = lon
            max_speed = speed
            total_distance = 0.0
            speed_readings = [speed]
            
            # Find when trip ends (vehicle stops)
            j = i + 1
            last_lat, last_lon = lat, lon
            
            while j < len(rows) and rows[j][3] > 1.0:
                current_time, current_lat, current_lon, current_speed = rows[j]
                distance = calculate_distance(last_lat, last_lon, current_lat, current_lon)
                total_distance += distance
                max_speed = max(max_speed, current_speed)
                speed_readings.append(current_speed)
                last_lat, last_lon = current_lat, current_lon
                j += 1
            
            if j < len(rows):
                end_time = rows[j][0]
                end_lat = rows[j][1]
                end_lon = rows[j][2]
            else:
                end_time = rows[-1][0]
                end_lat = rows[-1][1]
                end_lon = rows[-1][2]
            
            # Calculate duration
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
            
            # Calculate average speed
            avg_speed = sum(speed_readings) / len(speed_readings) if speed_readings else 0
            
            if duration_minutes >= 5:  # Only record trips longer than 5 minutes
                trips.append({
                    'vehicle_id': vehicle_id,
                    'imei': imei,
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_lat': start_lat,
                    'start_lon': start_lon,
                    'end_lat': end_lat,
                    'end_lon': end_lon,
                    'distance_km': round(total_distance, 2),
                    'distance_miles': round(total_distance * 0.621371, 2),
                    'avg_speed': round(avg_speed, 2),
                    'max_speed': round(max_speed, 2),
                    'duration_minutes': duration_minutes
                })
            
            i = j
        else:
            i += 1
    
    return trips

# Engine control functions
def send_engine_command(vehicle_id, command):
    """Send engine command to a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO engine_control (vehicle_id, command, timestamp, status)
        VALUES (?, ?, CURRENT_TIMESTAMP, 'pending')
    ''', (vehicle_id, command))
    
    command_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Simulate response (in real implementation, this would communicate with device)
    simulate_engine_response(command_id)
    
    return command_id

def simulate_engine_response(command_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Simulate processing delay
    import time
    time.sleep(1)
    
    # Simulate response
    response = 'Engine command sent successfully'
    status = 'executed'
    executed_at = datetime.datetime.utcnow().isoformat()
    
    c.execute('''
        UPDATE engine_control 
        SET status = ?, response = ?, executed_at = ?
        WHERE id = ?
    ''', (status, response, executed_at, command_id))
    
    conn.commit()
    conn.close()

def get_engine_status(vehicle_id):
    """Get latest engine status for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT command, status, response, executed_at FROM engine_control 
        WHERE vehicle_id = ? 
        ORDER BY timestamp DESC LIMIT 1
    ''', (vehicle_id,))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        command, status, response, executed_at = result
        
        # Determine actual engine state based on last command
        if command == 'cut' and status == 'executed':
            engine_state = 'Cut'
        elif command == 'start' and status == 'executed':
            engine_state = 'Active'
        elif status == 'pending':
            engine_state = f'Processing {command}'
        elif status == 'failed':
            engine_state = f'Failed ({command})'
        else:
            engine_state = 'Unknown'
            
        return {
            'status': engine_state,
            'command': command,
            'response': response,
            'executed_at': executed_at
        }
    
    return {'status': 'Unknown', 'command': None, 'response': None, 'executed_at': None}

def set_speed_limit(vehicle_id, speed_limit_kmh, set_by):
    """Set speed limit for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Deactivate existing limits for this vehicle
    c.execute('''
        UPDATE speed_limits SET is_active = 0 WHERE vehicle_id = ?
    ''', (vehicle_id,))
    
    # Insert new speed limit
    c.execute('''
        INSERT INTO speed_limits (vehicle_id, speed_limit_kmh, set_by, set_at, is_active)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1)
    ''', (vehicle_id, speed_limit_kmh, set_by))
    
    limit_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return limit_id

def get_speed_limit(vehicle_id):
    """Get current speed limit for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT speed_limit_kmh, set_by, set_at FROM speed_limits 
        WHERE vehicle_id = ? AND is_active = 1 
        ORDER BY set_at DESC LIMIT 1
    ''', (vehicle_id,))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        speed_limit, set_by, set_at = result
        return {
            'speed_limit': speed_limit,
            'set_by': set_by,
            'set_at': set_at
        }
    
    # Return None when no active speed limit found
    return None

def get_positioning_data(vehicle_id):
    """Get positioning data for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT current_latitude, current_longitude, last_latitude, last_longitude, 
               timestamp, heading, altitude FROM positioning_data 
        WHERE vehicle_id = ?
        ORDER BY timestamp DESC LIMIT 1
    ''', (vehicle_id,))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        current_lat, current_lon, last_lat, last_lon, timestamp, heading, altitude = result
        return {
            'current_latitude': current_lat,
            'current_longitude': current_lon,
            'last_latitude': last_lat,
            'last_longitude': last_lon,
            'timestamp': timestamp,
            'heading': heading,
            'altitude': altitude
        }
    
    return None

def log_alarm(vehicle_id, alarm_type, message):
    """Log an alarm for a vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO alarm_logs (vehicle_id, alarm_type, message, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (vehicle_id, alarm_type, message))
    
    alarm_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return alarm_id

def get_alarm_logs(vehicle_id=None, limit=100):
    """Get alarm logs, optionally filtered by vehicle"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    if vehicle_id:
        c.execute('''
            SELECT a.id, a.vehicle_id, a.alarm_type, a.message, a.timestamp, a.acknowledged, a.acknowledged_by, a.acknowledged_at,
                   v.license_plate, v.imei
            FROM alarm_logs a
            JOIN vehicles v ON a.vehicle_id = v.id
            WHERE a.vehicle_id = ?
            ORDER BY a.timestamp DESC 
            LIMIT ?
        ''', (vehicle_id, limit))
    else:
        c.execute('''
            SELECT a.id, a.vehicle_id, a.alarm_type, a.message, a.timestamp, a.acknowledged, a.acknowledged_by, a.acknowledged_at,
                   v.license_plate, v.imei
            FROM alarm_logs a
            JOIN vehicles v ON a.vehicle_id = v.id
            ORDER BY a.timestamp DESC 
            LIMIT ?
        ''', (limit,))
    
    alarms = []
    for row in c.fetchall():
        alarms.append({
            'id': row[0],
            'vehicle_id': row[1],
            'alarm_type': row[2],
            'message': row[3],
            'timestamp': row[4],
            'acknowledged': row[5],
            'acknowledged_by': row[6],
            'acknowledged_at': row[7],
            'license_plate': row[8],
            'imei': row[9]
        })
    
    conn.close()
    return alarms

def create_trip_request(department, requester_name, purpose, destination):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    request_date = datetime.datetime.utcnow().isoformat()
    
    c.execute('''
        INSERT INTO trip_requests (department, requester_name, request_date, purpose, destination)
        VALUES (?, ?, ?, ?, ?)
    ''', (department, requester_name, request_date, purpose, destination))
    
    conn.commit()
    request_id = c.lastrowid
    conn.close()
    
    return request_id

def get_trip_requests(status=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    if status:
        c.execute('''
            SELECT id, department, requester_name, request_date, purpose, destination, status, approved_by, approved_at, vehicle_assigned
            FROM trip_requests 
            WHERE status = ?
            ORDER BY request_date DESC
        ''', (status,))
    else:
        c.execute('''
            SELECT id, department, requester_name, request_date, purpose, destination, status, approved_by, approved_at, vehicle_assigned
            FROM trip_requests 
            ORDER BY request_date DESC
        ''')
    
    rows = c.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'department': row[1],
        'requester_name': row[2],
        'request_date': row[3],
        'purpose': row[4],
        'destination': row[5],
        'status': row[6],
        'approved_by': row[7],
        'approved_at': row[8],
        'vehicle_assigned': row[9]
    } for row in rows]

# Vehicle CRUD functions
def create_vehicle(vehicle_data):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT INTO vehicles (
                imei, license_plate, make, model, year, color, vehicle_type,
                driver_name, driver_contact, department, status, fuel_capacity,
                current_fuel, mileage, last_service_date, next_service_date,
                insurance_expiry, registration_expiry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vehicle_data['imei'],
            vehicle_data.get('license_plate'),
            vehicle_data.get('make'),
            vehicle_data.get('model'),
            vehicle_data.get('year'),
            vehicle_data.get('color'),
            vehicle_data.get('vehicle_type'),
            vehicle_data.get('driver_name'),
            vehicle_data.get('driver_contact'),
            vehicle_data.get('department'),
            vehicle_data.get('status', 'active'),
            vehicle_data.get('fuel_capacity'),
            vehicle_data.get('current_fuel', 0),
            vehicle_data.get('mileage', 0),
            vehicle_data.get('last_service_date'),
            vehicle_data.get('next_service_date'),
            vehicle_data.get('insurance_expiry'),
            vehicle_data.get('registration_expiry')
        ))
        
        conn.commit()
        vehicle_id = c.lastrowid
        return vehicle_id
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if 'UNIQUE constraint failed: vehicles.imei' in str(e):
            raise ValueError('A vehicle with this IMEI already exists')
        else:
            raise e
    finally:
        conn.close()

def get_all_vehicles(status=None, department=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT id, imei, license_plate, make, model, year, color, vehicle_type,
               driver_name, driver_contact, department, status, fuel_capacity,
               current_fuel, mileage, last_service_date, next_service_date,
               insurance_expiry, registration_expiry, created_at, updated_at
        FROM vehicles
        WHERE 1=1
    '''
    params = []
    
    if status:
        query += ' AND status = ?'
        params.append(status)
    
    if department:
        query += ' AND department = ?'
        params.append(department)
    
    query += ' ORDER BY created_at DESC'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'imei': row[1],
        'license_plate': row[2],
        'make': row[3],
        'model': row[4],
        'year': row[5],
        'color': row[6],
        'vehicle_type': row[7],
        'driver_name': row[8],
        'driver_contact': row[9],
        'department': row[10],
        'status': row[11],
        'fuel_capacity': row[12],
        'current_fuel': row[13],
        'mileage': row[14],
        'last_service_date': row[15],
        'next_service_date': row[16],
        'insurance_expiry': row[17],
        'registration_expiry': row[18],
        'created_at': row[19],
        'updated_at': row[20]
    } for row in rows]

def get_vehicle_by_id(vehicle_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT id, imei, license_plate, make, model, year, color, vehicle_type,
               driver_name, driver_contact, department, status, fuel_capacity,
               current_fuel, mileage, last_service_date, next_service_date,
               insurance_expiry, registration_expiry, created_at, updated_at
        FROM vehicles WHERE id = ?
    ''', (vehicle_id,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'imei': row[1],
            'license_plate': row[2],
            'make': row[3],
            'model': row[4],
            'year': row[5],
            'color': row[6],
            'vehicle_type': row[7],
            'driver_name': row[8],
            'driver_contact': row[9],
            'department': row[10],
            'status': row[11],
            'fuel_capacity': row[12],
            'current_fuel': row[13],
            'mileage': row[14],
            'last_service_date': row[15],
            'next_service_date': row[16],
            'insurance_expiry': row[17],
            'registration_expiry': row[18],
            'created_at': row[19],
            'updated_at': row[20]
        }
    return None

def get_vehicle_id_from_imei(imei):
    """Get vehicle_id from IMEI, return None if not found"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('SELECT id FROM vehicles WHERE imei = ?', (imei,))
    result = c.fetchone()
    conn.close()
    
    return result[0] if result else None

def get_vehicle_by_imei(imei):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''
        SELECT id, imei, license_plate, make, model, year, color, vehicle_type,
               driver_name, driver_contact, department, status, fuel_capacity,
               current_fuel, mileage, last_service_date, next_service_date,
               insurance_expiry, registration_expiry, created_at, updated_at
        FROM vehicles WHERE imei = ?
    ''', (imei,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'imei': row[1],
            'license_plate': row[2],
            'make': row[3],
            'model': row[4],
            'year': row[5],
            'color': row[6],
            'vehicle_type': row[7],
            'driver_name': row[8],
            'driver_contact': row[9],
            'department': row[10],
            'status': row[11],
            'fuel_capacity': row[12],
            'current_fuel': row[13],
            'mileage': row[14],
            'last_service_date': row[15],
            'next_service_date': row[16],
            'insurance_expiry': row[17],
            'registration_expiry': row[18],
            'created_at': row[19],
            'updated_at': row[20]
        }
    return None

def update_vehicle(vehicle_id, vehicle_data):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Build dynamic update query
    update_fields = []
    params = []
    
    for field, value in vehicle_data.items():
        if field != 'id' and field != 'imei':  # Don't update ID or IMEI
            update_fields.append(f'{field} = ?')
            params.append(value)
    
    if not update_fields:
        return False  # No fields to update
    
    # Add updated timestamp
    update_fields.append('updated_at = ?')
    params.append(datetime.datetime.utcnow().isoformat())
    
    # Add vehicle_id for WHERE clause
    params.append(vehicle_id)
    
    query = f'UPDATE vehicles SET {', '.join(update_fields)} WHERE id = ?'
    
    try:
        c.execute(query, params)
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()

def delete_vehicle(vehicle_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    try:
        c.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()

def get_vehicle_statistics():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Get total vehicles by status
    c.execute('''
        SELECT status, COUNT(*) as count
        FROM vehicles
        GROUP BY status
    ''')
    status_counts = dict(c.fetchall())
    
    # Get vehicles by department
    c.execute('''
        SELECT department, COUNT(*) as count
        FROM vehicles
        WHERE department IS NOT NULL
        GROUP BY department
    ''')
    dept_counts = dict(c.fetchall())
    
    # Get vehicles by type
    c.execute('''
        SELECT vehicle_type, COUNT(*) as count
        FROM vehicles
        WHERE vehicle_type IS NOT NULL
        GROUP BY vehicle_type
    ''')
    type_counts = dict(c.fetchall())
    
    conn.close()
    
    return {
        'status_counts': status_counts,
        'department_counts': dept_counts,
        'vehicle_type_counts': type_counts,
        'total_vehicles': sum(status_counts.values())
    }

@app.route('/')
def index():
    return render_template('dashboard.html')

# API endpoint for latest GPS points
@app.route('/api/latest')
@app.route('/api/points')
def api_points():
    return jsonify(get_latest(200))

# Park Report API
@app.route('/api/reports/parking')
def parking_report():
    imei = request.args.get('imei')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    events = detect_parking_events(imei, start_date, end_date)
    return jsonify({
        'imei': imei,
        'start_date': start_date,
        'end_date': end_date,
        'parking_events': events,
        'total_events': len(events)
    })

# Daily Mileage Report API
@app.route('/api/reports/mileage')
def mileage_report():
    imei = request.args.get('imei')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    mileage_data = get_daily_mileage(imei, start_date, end_date)
    total_miles = sum(day['miles'] for day in mileage_data)
    
    return jsonify({
        'imei': imei,
        'start_date': start_date,
        'end_date': end_date,
        'daily_mileage': mileage_data,
        'total_miles': round(total_miles, 2)
    })

# Trip Reports API
@app.route('/api/reports/trips')
def trips_report():
    imei = request.args.get('imei')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    trips = get_trip_summary(imei, start_date, end_date)
    total_distance = sum(trip['distance_miles'] for trip in trips)
    total_duration = sum(trip['duration_minutes'] for trip in trips)
    
    return jsonify({
        'imei': imei,
        'start_date': start_date,
        'end_date': end_date,
        'trips': trips,
        'total_trips': len(trips),
        'total_distance_miles': round(total_distance, 2),
        'total_duration_minutes': total_duration
    })

# Fuel Report API (placeholder for future fuel sensor integration)
@app.route('/api/reports/fuel')
def fuel_report():
    imei = request.args.get('imei')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, fuel_level, fuel_filled, fuel_drained, event_type
        FROM fuel_data 
        WHERE vehicle_id = ?
    '''
    params = [vehicle_id]
    
    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)
    
    query += ' ORDER BY timestamp'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    fuel_data = []
    total_filled = 0.0
    total_drained = 0.0
    
    for row in rows:
        timestamp, fuel_level, fuel_filled, fuel_drained, event_type = row
        fuel_data.append({
            'timestamp': timestamp,
            'fuel_level': fuel_level,
            'fuel_filled': fuel_filled,
            'fuel_drained': fuel_drained,
            'event_type': event_type
        })
        total_filled += fuel_filled or 0
        total_drained += fuel_drained or 0
    
    return jsonify({
        'imei': imei,
        'start_date': start_date,
        'end_date': end_date,
        'fuel_data': fuel_data,
        'total_filled': round(total_filled, 2),
        'total_drained': round(total_drained, 2),
        'net_consumption': round(total_filled - total_drained, 2)
    })

# Temperature Report API (placeholder for future temperature sensor integration)
@app.route('/api/reports/temperature')
def temperature_report():
    imei = request.args.get('imei')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, temperature_celsius, sensor_id
        FROM temperature_data 
        WHERE vehicle_id = ?
    '''
    params = [vehicle_id]
    
    if start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)
    
    query += ' ORDER BY timestamp'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    temp_data = []
    temps = []
    
    for row in rows:
        timestamp, temp_celsius, sensor_id = row
        temp_data.append({
            'timestamp': timestamp,
            'temperature_celsius': temp_celsius,
            'sensor_id': sensor_id
        })
        if temp_celsius is not None:
            temps.append(temp_celsius)
    
    avg_temp = sum(temps) / len(temps) if temps else None
    min_temp = min(temps) if temps else None
    max_temp = max(temps) if temps else None
    
    return jsonify({
        'imei': imei,
        'start_date': start_date,
        'end_date': end_date,
        'temperature_data': temp_data,
        'readings_count': len(temp_data),
        'average_temperature': round(avg_temp, 2) if avg_temp else None,
        'min_temperature': min_temp,
        'max_temperature': max_temp
    })

# Engine Control APIs
@app.route('/api/engine/cut', methods=['POST'])
def cut_engine():
    data = request.get_json()
    imei = data.get('imei')
    user = data.get('user', 'system')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle_id = get_vehicle_id_from_imei(imei)
    if not vehicle_id:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    command_id = send_engine_command(vehicle_id, 'cut')
    
    return jsonify({
        'success': True,
        'command_id': command_id,
        'message': 'Engine cut command sent successfully'
    })

@app.route('/api/engine/start', methods=['POST'])
def start_engine():
    data = request.get_json()
    imei = data.get('imei')
    
    if not imei:
        return jsonify({'error': 'IMEI is required'}), 400
    
    # Get vehicle_id from imei
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404
    
    try:
        command_id = send_engine_command(vehicle['id'], 'start')
        return jsonify({
            'message': 'Engine start command sent successfully',
            'command_id': command_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/engine/status', methods=['GET'])
def engine_status():
    imei = request.args.get('imei')
    
    if not imei:
        return jsonify({'error': 'IMEI is required'}), 400
    
    # Get vehicle_id from imei
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404
    
    try:
        status = get_engine_status(vehicle['id'])
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Speed Limit APIs
@app.route('/api/speed_limit', methods=['POST'])
def set_speed_limit_api():
    data = request.get_json()
    imei = data.get('imei')
    speed_limit_kmh = data.get('speed_limit')
    set_by = data.get('user', 'system')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    if not speed_limit_kmh:
        return jsonify({'error': 'Speed limit is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    try:
        set_speed_limit(vehicle['id'], speed_limit_kmh, set_by)
        return jsonify({
            'success': True,
            'message': 'Speed limit set successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/speed_limit', methods=['GET'])
def get_speed_limit_api():
    imei = request.args.get('imei')
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    try:
        speed_limit_data = get_speed_limit(vehicle['id'])
        if speed_limit_data:
            return jsonify(speed_limit_data)
        else:
            return jsonify({
                'speed_limit': None,
                'set_by': None,
                'set_at': None,
                'message': 'No speed limit set for this vehicle'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Alarms API
@app.route('/api/alarms', methods=['GET'])
def get_alarms():
    imei = request.args.get('imei')
    limit = request.args.get('limit', 100)
    
    if not imei:
        return jsonify({'error': 'IMEI parameter is required'}), 400
    
    # Get vehicle_id from IMEI for normalization
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found for IMEI'}), 404
    
    try:
        limit = int(limit)
        alarms = get_alarm_logs(vehicle['id'], limit)
        return jsonify({'alarms': alarms})
    except ValueError:
        return jsonify({'error': 'Invalid limit parameter'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ... (rest of the code remains the same)

@app.route('/api/positioning', methods=['GET'])
def positioning():
    imei = request.args.get('imei')
    
    if not imei:
        return jsonify({'error': 'IMEI is required'}), 400
    
    # Get vehicle_id from imei
    vehicle = get_vehicle_by_imei(imei)
    if not vehicle:
        return jsonify({'error': 'Vehicle not found'}), 404
    
    try:
        data = get_positioning_data(vehicle['id'])
        if data:
            return jsonify(data)
        else:
            return jsonify({'error': 'No positioning data available for this vehicle'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ... (rest of the code remains the same)

@app.route('/api/alarms/acknowledge', methods=['POST'])
def acknowledge_alarm():
    data = request.get_json()
    alarm_id = data.get('alarm_id')
    acknowledged_by = data.get('acknowledged_by')
    
    if not all([alarm_id, acknowledged_by]):
        return jsonify({'error': 'alarm_id and acknowledged_by are required'}), 400
    
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        c.execute('''
            UPDATE alarm_logs 
            SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (acknowledged_by, alarm_id))
        
        conn.commit()
        conn.close()
        
        if c.rowcount > 0:
            return jsonify({'message': 'Alarm acknowledged successfully'})
        else:
            return jsonify({'error': 'Alarm not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vehicles', methods=['GET', 'POST'])
def vehicles_api():
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided for vehicle creation'}), 400
        
        # Validate required fields
        required_fields = ['imei']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        try:
            vehicle_id = create_vehicle(data)
            return jsonify({
                'success': True,
                'message': 'Vehicle created successfully',
                'vehicle_id': vehicle_id
            }), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': 'Failed to create vehicle: ' + str(e)}), 500
    
    else:  # GET
        status = request.args.get('status')
        department = request.args.get('department')
        
        try:
            vehicles = get_all_vehicles(status, department)
            return jsonify({
                'vehicles': vehicles,
                'total_count': len(vehicles),
                'filters': {
                    'status': status,
                    'department': department
                }
            })
        except Exception as e:
            return jsonify({'error': 'Failed to fetch vehicles: ' + str(e)}), 500

@app.route('/api/vehicles/<int:vehicle_id>')
def get_vehicle_api(vehicle_id):
    try:
        vehicle = get_vehicle_by_id(vehicle_id)
        if vehicle:
            return jsonify({
                'vehicle': vehicle,
                'success': True
            })
        else:
            return jsonify({'error': 'Vehicle not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vehicle: ' + str(e)}), 500

@app.route('/api/vehicles/imei/<imei>')
def get_vehicle_by_imei_api(imei):
    try:
        vehicle = get_vehicle_by_imei(imei)
        if vehicle:
            return jsonify({
                'vehicle': vehicle,
                'success': True
            })
        else:
            return jsonify({'error': 'Vehicle not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vehicle: ' + str(e)}), 500

@app.route('/api/vehicles/<int:vehicle_id>', methods=['PUT'])
def update_vehicle_api(vehicle_id):
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided for update'}), 400
    
    try:
        success = update_vehicle(vehicle_id, data)
        if success:
            return jsonify({
                'success': True,
                'message': 'Vehicle updated successfully'
            })
        else:
            return jsonify({'error': 'Vehicle not found or no changes made'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to update vehicle: ' + str(e)}), 500

@app.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
def delete_vehicle_api(vehicle_id):
    try:
        success = delete_vehicle(vehicle_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Vehicle deleted successfully'
            })
        else:
            return jsonify({'error': 'Vehicle not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete vehicle: ' + str(e)}), 500

@app.route('/api/vehicles/statistics')
def get_vehicle_statistics_api():
    try:
        stats = get_vehicle_statistics()
        return jsonify({
            'statistics': stats,
            'success': True
        })
    except Exception as e:
        return jsonify({'error': 'Failed to fetch vehicle statistics: ' + str(e)}), 500

# Initialize alarm system
add_alarm_routes(app)

if __name__ == '__main__':
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

