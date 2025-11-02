from flask import Flask, render_template, jsonify
import threading
from listener import start_server
import sqlite3

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

@app.route('/')
def index():
    return render_template('map.html')

# API endpoint for latest GPS points
@app.route('/api/latest')
@app.route('/api/points')
def api_points():
    return jsonify(get_latest(200))

if __name__ == '__main__':
    # Start TCP listener in a background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
