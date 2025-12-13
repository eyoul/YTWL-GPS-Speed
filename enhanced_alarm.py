# Enhanced alarm system with severity levels
import sqlite3
import datetime

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
    'emergency': {'severity': 'critical', 'category': 'emergency'}
}

def log_alarm_with_severity(vehicle_id, alarm_type, message, severity=None):
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
    
    c.execute('''
        INSERT INTO alarm_logs (vehicle_id, alarm_type, message, timestamp, severity, category)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (vehicle_id, alarm_type, message, datetime.datetime.now().isoformat(), severity, category))
    
    conn.commit()
    conn.close()

# Example usage in existing alarm functions
def enhanced_log_alarm(vehicle_id, alarm_type, message):
    """Wrapper function to maintain compatibility with existing code"""
    log_alarm_with_severity(vehicle_id, alarm_type, message)
