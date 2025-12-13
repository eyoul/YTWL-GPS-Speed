# Enhanced alarm system with severity levels
import sqlite3
import datetime
import json
from flask import request, jsonify

# Alarm severity levels
ALARM_SEVERITY = {
    'critical': 3,
    'warning': 2,
    'info': 1
}

# Alarm type classifications
ALARM_TYPES = {
    'speed_violation': {'severity': 'warning', 'category': 'safety'},
    'excessive_idling': {'severity': 'info', 'category': 'efficiency'},
    'unauthorized_movement': {'severity': 'critical', 'category': 'security'},
    'geofence_violation': {'severity': 'warning', 'category': 'compliance'},
    'maintenance_due': {'severity': 'info', 'category': 'maintenance'},
    'emergency': {'severity': 'critical', 'category': 'emergency'},
    'fuel_waste_prevention': {'severity': 'warning', 'category': 'efficiency'},
    'productivity_tracking': {'severity': 'info', 'category': 'efficiency'},
    'device_offline': {'severity': 'warning', 'category': 'connectivity'},
    'low_battery': {'severity': 'warning', 'category': 'maintenance'},
    'tamper_detection': {'severity': 'critical', 'category': 'security'}
}

def log_alarm_with_severity(vehicle_id, alarm_type, message, severity=None, metadata=None):
    """Enhanced alarm logging with severity levels and classification"""
    # Determine severity if not provided
    if not severity and alarm_type in ALARM_TYPES:
        severity = ALARM_TYPES[alarm_type]['severity']
    elif not severity:
        severity = 'info'  # default severity
    
    category = ALARM_TYPES.get(alarm_type, {}).get('category', 'general')
    
    print(f"[{severity.upper()} ALARM] Vehicle {vehicle_id}: {message}")
    
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    # Store metadata as JSON if provided
    metadata_json = json.dumps(metadata) if metadata else None
    
    c.execute('''
        INSERT INTO alarm_logs (vehicle_id, alarm_type, message, timestamp, severity, category, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, alarm_type, message, datetime.datetime.now().isoformat(), severity, category, metadata_json))
    
    conn.commit()
    conn.close()
    
    # Trigger immediate notifications for critical alarms
    if severity == 'critical':
        trigger_critical_notification(vehicle_id, alarm_type, message, metadata)

def trigger_critical_notification(vehicle_id, alarm_type, message, metadata=None):
    """Trigger immediate notifications for critical alarms"""
    # Here you can integrate with:
    # - SMS notifications
    # - Email alerts
    # - Push notifications
    # - Webhook calls
    
    notification_data = {
        'vehicle_id': vehicle_id,
        'alarm_type': alarm_type,
        'message': message,
        'severity': 'critical',
        'timestamp': datetime.datetime.now().isoformat(),
        'metadata': metadata
    }
    
    print(f"[CRITICAL NOTIFICATION] {json.dumps(notification_data, indent=2)}")
    
    # TODO: Add actual notification integrations:
    # - send_sms_notification(vehicle_id, message)
    # - send_email_alert(notification_data)
    # - call_webhook(notification_data)

def get_vehicle_alarms(vehicle_id, severity=None, category=None, limit=100):
    """Get alarms for a specific vehicle with filtering options"""
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    query = '''
        SELECT id, vehicle_id, alarm_type, message, timestamp, severity, category, 
               acknowledged, acknowledged_by, acknowledged_at, metadata
        FROM alarm_logs 
        WHERE vehicle_id = ?
    '''
    params = [vehicle_id]
    
    if severity:
        query += ' AND severity = ?'
        params.append(severity)
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    query += ' ORDER BY timestamp DESC LIMIT ?'
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    alarms = []
    for row in rows:
        alarm = {
            'id': row[0],
            'vehicle_id': row[1],
            'alarm_type': row[2],
            'message': row[3],
            'timestamp': row[4],
            'severity': row[5],
            'category': row[6],
            'acknowledged': bool(row[7]),
            'acknowledged_by': row[8],
            'acknowledged_at': row[9],
            'metadata': json.loads(row[10]) if row[10] else None
        }
        alarms.append(alarm)
    
    return alarms

def get_all_alarms(severity=None, category=None, acknowledged=None, limit=100):
    """Get all alarms with filtering options"""
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    query = '''
        SELECT a.id, a.vehicle_id, a.alarm_type, a.message, a.timestamp, a.severity, a.category,
               a.acknowledged, a.acknowledged_by, a.acknowledged_at, a.metadata,
               v.license_plate, v.imei
        FROM alarm_logs a
        JOIN vehicles v ON a.vehicle_id = v.id
        WHERE 1=1
    '''
    params = []
    
    if severity:
        query += ' AND a.severity = ?'
        params.append(severity)
    
    if category:
        query += ' AND a.category = ?'
        params.append(category)
    
    if acknowledged is not None:
        query += ' AND a.acknowledged = ?'
        params.append(1 if acknowledged else 0)
    
    query += ' ORDER BY a.timestamp DESC LIMIT ?'
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    alarms = []
    for row in rows:
        alarm = {
            'id': row[0],
            'vehicle_id': row[1],
            'alarm_type': row[2],
            'message': row[3],
            'timestamp': row[4],
            'severity': row[5],
            'category': row[6],
            'acknowledged': bool(row[7]),
            'acknowledged_by': row[8],
            'acknowledged_at': row[9],
            'metadata': json.loads(row[10]) if row[10] else None,
            'license_plate': row[11],
            'imei': row[12]
        }
        alarms.append(alarm)
    
    return alarms

def acknowledge_alarm(alarm_id, acknowledged_by):
    """Acknowledge an alarm"""
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    c.execute('''
        UPDATE alarm_logs 
        SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
        WHERE id = ?
    ''', (acknowledged_by, datetime.datetime.now().isoformat(), alarm_id))
    
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

def get_alarm_statistics(vehicle_id=None, days=7):
    """Get alarm statistics for dashboard"""
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    since_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    
    if vehicle_id:
        query = '''
            SELECT severity, category, COUNT(*) as count
            FROM alarm_logs 
            WHERE vehicle_id = ? AND timestamp >= ?
            GROUP BY severity, category
        '''
        c.execute(query, (vehicle_id, since_date))
    else:
        query = '''
            SELECT severity, category, COUNT(*) as count
            FROM alarm_logs 
            WHERE timestamp >= ?
            GROUP BY severity, category
        '''
        c.execute(query, (since_date,))
    
    rows = c.fetchall()
    conn.close()
    
    stats = {
        'total_alarms': 0,
        'by_severity': {'critical': 0, 'warning': 0, 'info': 0},
        'by_category': {},
        'period_days': days
    }
    
    for severity, category, count in rows:
        stats['total_alarms'] += count
        stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + count
        stats['by_category'][category] = stats['by_category'].get(category, 0) + count
    
    return stats

def check_device_offline_alarms():
    """Check for devices that haven't reported data recently"""
    conn = sqlite3.connect('gps.db')
    c = conn.cursor()
    
    # Check devices with no data in last 30 minutes
    cutoff_time = (datetime.datetime.now() - datetime.timedelta(minutes=30)).isoformat()
    
    c.execute('''
        SELECT DISTINCT v.id, v.license_plate, v.imei
        FROM vehicles v
        LEFT JOIN gps_data g ON v.id = g.vehicle_id AND g.timestamp >= ?
        WHERE g.vehicle_id IS NULL
    ''', (cutoff_time,))
    
    offline_vehicles = c.fetchall()
    conn.close()
    
    for vehicle_id, license_plate, imei in offline_vehicles:
        # Check if we already logged this alarm recently (avoid spam)
        recent_offline_alarm = get_vehicle_alarms(
            vehicle_id, 
            alarm_type='device_offline', 
            limit=1
        )
        
        if not recent_offline_alarm:
            log_alarm_with_severity(
                vehicle_id, 
                'device_offline', 
                f'Vehicle {license_plate} ({imei}) has not reported data for over 30 minutes',
                severity='warning',
                metadata={'last_seen': cutoff_time}
            )

def enhanced_log_alarm(vehicle_id, alarm_type, message, severity=None, metadata=None):
    """Wrapper function to maintain compatibility with existing code"""
    log_alarm_with_severity(vehicle_id, alarm_type, message, severity, metadata)

# Flask API endpoints for alarm management
def add_alarm_routes(app):
    """Add alarm management routes to Flask app"""
    
    @app.route('/api/alarms')
    def get_alarms_api():
        """Get alarms with filtering"""
        vehicle_id = request.args.get('vehicle_id', type=int)
        severity = request.args.get('severity')
        category = request.args.get('category')
        acknowledged = request.args.get('acknowledged')
        
        if vehicle_id:
            alarms = get_vehicle_alarms(vehicle_id, severity, category)
        else:
            acknowledged_bool = None if acknowledged is None else acknowledged.lower() == 'true'
            alarms = get_all_alarms(severity, category, acknowledged_bool)
        
        return jsonify({'alarms': alarms, 'total': len(alarms)})
    
    @app.route('/api/alarms/<int:alarm_id>/acknowledge', methods=['POST'])
    def acknowledge_alarm_api(alarm_id):
        """Acknowledge an alarm"""
        data = request.get_json()
        acknowledged_by = data.get('acknowledged_by', 'System')
        
        success = acknowledge_alarm(alarm_id, acknowledged_by)
        
        if success:
            return jsonify({'success': True, 'message': 'Alarm acknowledged'})
        else:
            return jsonify({'success': False, 'message': 'Alarm not found'}), 404
    
    @app.route('/api/alarms/statistics')
    def alarm_statistics_api():
        """Get alarm statistics"""
        vehicle_id = request.args.get('vehicle_id', type=int)
        days = request.args.get('days', 7, type=int)
        
        stats = get_alarm_statistics(vehicle_id, days)
        return jsonify(stats)
