from flask import Flask, render_template, jsonify, request
import threading
from listener import start_server
import sqlite3
import datetime
import math

app = Flask(__name__)
DB = 'gps.db'

def save_gps(imei, timestamp, lat, lon, speed):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO gps_data (imei, timestamp, latitude, longitude, speed)
        VALUES (?, ?, ?, ?, ?)
    ''', (imei, timestamp, lat, lon, speed))
    conn.commit()
    conn.close()
    
def get_latest(limit=100):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        SELECT imei, timestamp, latitude, longitude, speed 
        FROM gps_data 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL 
        ORDER BY id DESC 
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'imei': r[0], 'timestamp': r[1], 'lat': r[2], 'lon': r[3], 'speed': r[4]} for r in rows]

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def detect_parking_events(imei, start_date=None, end_date=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, latitude, longitude, speed 
        FROM gps_data 
        WHERE imei = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
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
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT DATE(timestamp) as date, latitude, longitude, speed
        FROM gps_data 
        WHERE imei = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
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
    
    return [{'date': date, 'miles': round(km * 0.621371, 2)} for date, km in daily_mileage.items()]

def get_trip_summary(imei, start_date=None, end_date=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, latitude, longitude, speed
        FROM gps_data 
        WHERE imei = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
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

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/map')
def map_view():
    return render_template('map.html')

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
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, fuel_level, fuel_filled, fuel_drained, event_type
        FROM fuel_data 
        WHERE imei = ?
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
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    query = '''
        SELECT timestamp, temperature_celsius, sensor_id
        FROM temperature_data 
        WHERE imei = ?
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

if __name__ == '__main__':
    # Start TCP listener in a background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
