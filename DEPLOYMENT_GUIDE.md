# YTWL GPS Speed Limiter Deployment Guide

## System Overview
Your system is ready to test with YTWL GPS Speed Limiter model YTWL_CA10F on AWS.

## Current Architecture
- **Flask Web App**: Dashboard with Leaflet.js + OpenStreetMap
- **TCP Listener**: Port 9000 for GPS device communication
- **SQLite Database**: Stores GPS data, vehicles, alarms, reports
- **Real-time Features**: Speed limiting, engine control, alarms

## YTWL_CA10F Device Integration

### 1. Device Configuration
The YTWL_CA10F typically sends GPS data via TCP in these formats:
- **Binary Protocol**: GT06-like binary packets
- **CSV Protocol**: Text-based comma-separated values
- **Port**: Usually TCP 9000 (configurable in device)

### 2. Data Formats Supported

#### CSV Format (Recommended for testing)
```
IMEI,timestamp,latitude,longitude,speed
862123456789012,2025-12-13T22:15:00Z,9.0331,38.7500,45.5
```

#### Binary GT06 Protocol
Your listener already supports GT06 binary parsing with automatic detection.

### 3. AWS Deployment Steps

#### Step 1: Prepare AWS EC2 Instance
```bash
# Launch EC2 instance (Ubuntu 20.04 LTS recommended)
# Security Group: Open ports 80, 443, 9000
# Instance type: t3.micro or larger

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3 python3-pip sqlite3 nginx -y
pip3 install flask

# Clone your repository
git clone <your-repo-url>
cd YTWL-GPS-Speed
```

#### Step 2: Configure Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask

# Make app accessible from external IPs
# Edit app.py to bind to 0.0.0.0 (already done)
```

#### Step 3: Set up System Services
```bash
# Create systemd service for GPS listener
sudo tee /etc/systemd/system/gps-listener.service > /dev/null <<EOF
[Unit]
Description=GPS Listener Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/YTWL-GPS-Speed
Environment=PATH=/home/ubuntu/YTWL-GPS-Speed/venv/bin
ExecStart=/home/ubuntu/YTWL-GPS-Speed/venv/bin/python listener.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Flask app
sudo tee /etc/systemd/system/gps-webapp.service > /dev/null <<EOF
[Unit]
Description=GPS Web App Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/YTWL-GPS-Speed
Environment=PATH=/home/ubuntu/YTWL-GPS-Speed/venv/bin
ExecStart=/home/ubuntu/YTWL-GPS-Speed/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start services
sudo systemctl daemon-reload
sudo systemctl enable gps-listener gps-webapp
sudo systemctl start gps-listener gps-webapp
```

#### Step 4: Configure Nginx Reverse Proxy
```bash
sudo tee /etc/nginx/sites-available/gps-app > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/gps-app /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 4. YTWL_CA10F Device Setup

#### Configure Device Settings
1. **Server IP**: Your AWS EC2 public IP
2. **Server Port**: 9000
3. **Protocol**: TCP
4. **Data Format**: CSV (easier for testing)
5. **Update Interval**: 30-60 seconds

#### Sample Device Configuration
```
Server: your-aws-ip:9000
Protocol: TCP
Format: CSV
Interval: 30s
```

### 5. Testing Procedure

#### Step 1: Add Test Vehicle
```bash
# Add a test vehicle to the database
curl -X POST http://your-domain.com/api/vehicles \
  -H "Content-Type: application/json" \
  -d '{
    "imei": "862123456789012",
    "license_plate": "TEST-001",
    "make": "YTWL",
    "model": "CA10F",
    "year": 2024,
    "vehicle_type": "Speed Limiter",
    "driver_name": "Test Driver",
    "department": "Testing"
  }'
```

#### Step 2: Test Data Transmission
```bash
# Send test GPS data via telnet
telnet your-aws-ip 9000
# Then type:
862123456789012,2025-12-13T22:15:00Z,9.0331,38.7500,45.5

# Or use netcat
echo "862123456789012,2025-12-13T22:15:00Z,9.0331,38.7500,45.5" | nc your-aws-ip 9000
```

#### Step 3: Verify Data Reception
```bash
# Check API endpoint
curl http://your-domain.com/api/latest

# Should return:
[{"imei": "862123456789012", "license_plate": "TEST-001", "timestamp": "...", "lat": 9.0331, "lon": 38.7500, "speed": 45.5}]
```

### 6. Monitoring and Logs

#### Check Service Status
```bash
sudo systemctl status gps-listener
sudo systemctl status gps-webapp

# View logs
sudo journalctl -u gps-listener -f
sudo journalctl -u gps-webapp -f
```

#### Monitor GPS Data
```bash
# Real-time GPS data monitoring
tail -f /var/log/syslog | grep GPS
```

### 7. Security Considerations

#### Firewall Setup
```bash
# Only allow necessary ports
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 9000
sudo ufw enable
```

#### SSL Certificate (Optional)
```bash
# Install Let's Encrypt for HTTPS
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 8. Troubleshooting

#### Common Issues
1. **Device not connecting**: Check firewall and port 9000
2. **No data showing**: Verify vehicle IMEI exists in database
3. **Map not loading**: Check browser console for errors
4. **Binary data issues**: Device may use different protocol

#### Debug Commands
```bash
# Check if port is listening
sudo netstat -tlnp | grep 9000

# Test connection
telnet your-aws-ip 9000

# Check database
sqlite3 gps.db "SELECT * FROM vehicles;"
sqlite3 gps.db "SELECT * FROM gps_data ORDER BY id DESC LIMIT 5;"
```

### 9. Performance Optimization

#### For Production Use
- Use PostgreSQL instead of SQLite
- Implement Redis for caching
- Add load balancing
- Set up monitoring with Prometheus/Grafana
- Configure automated backups

### 10. YTWL_CA10F Specific Features

Your system supports these YTWL features:
- **Speed Limiting**: Set and enforce speed limits
- **Engine Control**: Remote start/stop functionality
- **Real-time Tracking**: Live GPS position updates
- **Alarm System**: Speed violations, excessive idling
- **Trip Reports**: Distance, duration, fuel consumption
- **Geofencing**: Location-based alerts (can be extended)

### Next Steps
1. Deploy to AWS using this guide
2. Configure your YTWL_CA10F device
3. Test with real GPS data
4. Monitor system performance
5. Scale as needed

Your system is production-ready for the YTWL GPS Speed Limiter testing!
