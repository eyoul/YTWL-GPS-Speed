#!/usr/bin/env python3
"""
YTWL Device SMS Command Configuration
For configuring YTWL_CA10F GPS Speed Limiter via SMS
"""

import requests
import json
from datetime import datetime

class YTWLDeviceSMS:
    def __init__(self, web_app_url="http://localhost:5000"):
        self.web_app_url = web_app_url
        self.device_configs = {}
    
    def send_configuration_sms(self, device_imei, commands):
        """
        Send configuration SMS to YTWL device
        
        Args:
            device_imei: Device IMEI number
            commands: List of SMS commands to send
        """
        configuration = {
            "device_imei": device_imei,
            "commands": commands,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        # Store configuration for tracking
        self.device_configs[device_imei] = configuration
        
        print(f"Configuration SMS for device {device_imei}:")
        print("=" * 50)
        for cmd in commands:
            print(f"SMS: {cmd}")
        print("=" * 50)
        
        return configuration
    
    def get_standard_config(self, server_host, server_port, apn="etnet"):
        """
        Get standard YTWL device configuration commands
        
        Args:
            server_host: Your server hostname/IP
            server_port: Your server port (9000)
            apn: Mobile network APN
        """
        commands = [
            f"APN,1,{apn}#",
            f"SERVER,1,{server_host},{server_port}#",
            "CHECK#"
        ]
        return commands
    
    def get_advanced_config(self, server_host, server_port, apn="etnet", 
                          interval=60, heartbeat=300):
        """
        Get advanced YTWL device configuration
        
        Args:
            server_host: Your server hostname/IP
            server_port: Your server port (9000)
            apn: Mobile network APN
            interval: GPS update interval in seconds
            heartbeat: Heartbeat interval in seconds
        """
        commands = [
            f"APN,1,{apn}#",                    # Set APN
            f"SERVER,1,{server_host},{server_port}#",  # Set server
            f"INTERVAL,1,{interval}#",         # GPS update interval
            f"HEARTBEAT,1,{heartbeat}#",       # Heartbeat interval
            "TIMEZONE,1,3#",                   # Timezone (Ethiopia +3)
            "SPEEDLIMIT,1,80#",                # Default speed limit 80 km/h
            "CHECK#"                            # Check configuration
        ]
        return commands
    
    def get_engine_control_config(self):
        """Get engine control related commands"""
        commands = [
            "ENGINE,1,ON#",                    # Enable engine control
            "RELAY,1,2,5000#",                # Relay configuration
            "SPEEDLIMIT,1,60#",               # Speed limit for testing
            "CHECK#"
        ]
        return commands
    
    def get_monitoring_config(self):
        """Get monitoring and alarm configuration"""
        commands = [
            "ALARM,1,SPEED,ON#",              # Speed alarm
            "ALARM,1,GEO,ON#",                # Geofence alarm
            "ALARM,1,PWR,ON#",                # Power alarm
            "ALARM,1,SOS,ON#",                # SOS alarm
            "GEOFENCE,1,ADD,HOME,9.0331,38.7500,1000#",  # Add geofence
            "CHECK#"
        ]
        return commands
    
    def reset_device_config(self):
        """Reset device to factory defaults"""
        commands = [
            "RESET,1,FACTORY#",
            "REBOOT,1#"
        ]
        return commands
    
    def test_device_communication(self, device_imei):
        """Test basic device communication"""
        commands = [
            "STATUS#",
            "GPS,1,ON#",
            "CHECK#"
        ]
        return self.send_configuration_sms(device_imei, commands)

# Example usage and templates
def main():
    """Example usage of YTWL SMS configuration"""
    
    # Initialize SMS commander
    sms = YTWLDeviceSMS()
    
    # Your server details (update with your AWS/cloud details)
    SERVER_HOST = "your-aws-ip"  # or use ngrok for testing
    SERVER_PORT = "9000"
    DEVICE_IMEI = "862123456789012"  # Your YTWL device IMEI
    
    print("YTWL GPS Speed Limiter SMS Configuration")
    print("=" * 60)
    
    # 1. Basic Configuration
    print("\n1. BASIC CONFIGURATION:")
    basic_commands = sms.get_standard_config(SERVER_HOST, SERVER_PORT)
    sms.send_configuration_sms(DEVICE_IMEI, basic_commands)
    
    # 2. Advanced Configuration
    print("\n2. ADVANCED CONFIGURATION:")
    advanced_commands = sms.get_advanced_config(SERVER_HOST, SERVER_PORT)
    sms.send_configuration_sms(DEVICE_IMEI, advanced_commands)
    
    # 3. Engine Control Setup
    print("\n3. ENGINE CONTROL SETUP:")
    engine_commands = sms.get_engine_control_config()
    sms.send_configuration_sms(DEVICE_IMEI, engine_commands)
    
    # 4. Monitoring & Alarms
    print("\n4. MONITORING & ALARMS:")
    monitor_commands = sms.get_monitoring_config()
    sms.send_configuration_sms(DEVICE_IMEI, monitor_commands)
    
    print("\nConfiguration complete!")
    print(f"Send these SMS commands to device: {DEVICE_IMEI}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")

# SMS Command Reference
YTWL_COMMANDS = {
    # Network Configuration
    "APN": "APN,1,{apn}# - Set APN (e.g., APN,1,etnet#)",
    "SERVER": "SERVER,1,{host},{port}# - Set server IP and port",
    "INTERVAL": "INTERVAL,1,{seconds}# - GPS update interval",
    "HEARTBEAT": "HEARTBEAT,1,{seconds}# - Heartbeat interval",
    
    # Device Configuration
    "TIMEZONE": "TIMEZONE,1,{offset}# - Set timezone (3 for Ethiopia)",
    "SPEEDLIMIT": "SPEEDLIMIT,1,{kmh}# - Set speed limit",
    "RESET": "RESET,1,FACTORY# - Reset to factory defaults",
    "REBOOT": "REBOOT,1# - Reboot device",
    
    # Engine Control
    "ENGINE": "ENGINE,1,{ON|OFF}# - Enable/disable engine control",
    "RELAY": "RELAY,1,{id},{ms}# - Configure relay",
    
    # Monitoring
    "ALARM": "ALARM,1,{type},{ON|OFF}# - Enable/disable alarms",
    "GEOFENCE": "GEOFENCE,1,{ADD|DEL},{name},{lat},{lon},{radius}#",
    
    # Status Commands
    "STATUS": "STATUS# - Get device status",
    "GPS": "GPS,1,{ON|OFF}# - Turn GPS on/off",
    "CHECK": "CHECK# - Check current configuration",
    
    # Control Commands (for SMS gateway integration)
    "START": "START# - Start engine",
    "STOP": "STOP# - Stop engine",
    "LOCATE": "LOCATE# - Get current location"
}

if __name__ == "__main__":
    main()
