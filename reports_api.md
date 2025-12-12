# GPS Travel Reports API Documentation

This API provides comprehensive travel reports for GPS tracking data, including parking analysis, mileage tracking, fuel consumption, temperature monitoring, and trip summaries.

## Base URL
```
http://localhost:5000
```

## Authentication
No authentication required (for development)

## Report Endpoints

### 1. Park Report - Vehicle Stoppages and Idling Analysis
**GET** `/api/reports/parking`

Provides insights on vehicle stoppages and idling instances, including where and how long the vehicle stopped.

**Parameters:**
- `imei` (required): Vehicle IMEI number
- `start_date` (optional): Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- `end_date` (optional): End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)

**Example:**
```
GET /api/reports/parking?imei=123456789012345&start_date=2025-01-01&end_date=2025-01-07
```

**Response:**
```json
{
  "imei": "123456789012345",
  "start_date": "2025-01-01",
  "end_date": "2025-01-07",
  "parking_events": [
    {
      "imei": "123456789012345",
      "start_time": "2025-01-01T08:30:00",
      "end_time": "2025-01-01T09:15:00",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "duration_minutes": 45,
      "event_type": "idling"
    }
  ],
  "total_events": 1
}
```

### 2. Daily Mileage Report
**GET** `/api/reports/mileage`

Displays total miles driven for each vehicle for selected days.

**Parameters:**
- `imei` (required): Vehicle IMEI number
- `start_date` (optional): Start date in ISO format
- `end_date` (optional): End date in ISO format

**Example:**
```
GET /api/reports/mileage?imei=123456789012345&start_date=2025-01-01&end_date=2025-01-07
```

**Response:**
```json
{
  "imei": "123456789012345",
  "start_date": "2025-01-01",
  "end_date": "2025-01-07",
  "daily_mileage": [
    {"date": "2025-01-01", "miles": 45.2},
    {"date": "2025-01-02", "miles": 32.8}
  ],
  "total_miles": 78.0
}
```

### 3. Fuel Report
**GET** `/api/reports/fuel`

Shows fuel consumption, including total fuel filled and drained off.

**Parameters:**
- `imei` (required): Vehicle IMEI number
- `start_date` (optional): Start date in ISO format
- `end_date` (optional): End date in ISO format

**Example:**
```
GET /api/reports/fuel?imei=123456789012345&start_date=2025-01-01&end_date=2025-01-07
```

**Response:**
```json
{
  "imei": "123456789012345",
  "start_date": "2025-01-01",
  "end_date": "2025-01-07",
  "fuel_data": [
    {
      "timestamp": "2025-01-01T10:00:00",
      "fuel_level": 75.5,
      "fuel_filled": 0.0,
      "fuel_drained": 0.0,
      "event_type": "level"
    }
  ],
  "total_filled": 10.5,
  "total_drained": 2.3,
  "net_consumption": 8.2
}
```

### 4. Temperature Report
**GET** `/api/reports/temperature`

Monitors temperature settings for temperature-sensitive products.

**Parameters:**
- `imei` (required): Vehicle IMEI number
- `start_date` (optional): Start date in ISO format
- `end_date` (optional): End date in ISO format

**Example:**
```
GET /api/reports/temperature?imei=123456789012345&start_date=2025-01-01&end_date=2025-01-07
```

**Response:**
```json
{
  "imei": "123456789012345",
  "start_date": "2025-01-01",
  "end_date": "2025-01-07",
  "temperature_data": [
    {
      "timestamp": "2025-01-01T10:00:00",
      "temperature_celsius": 4.5,
      "sensor_id": "temp_001"
    }
  ],
  "readings_count": 1,
  "average_temperature": 4.5,
  "min_temperature": 4.5,
  "max_temperature": 4.5
}
```

### 5. Trip Reports
**GET** `/api/reports/trips`

Provides details on routes traveled, distance covered, and speed during trips.

**Parameters:**
- `imei` (required): Vehicle IMEI number
- `start_date` (optional): Start date in ISO format
- `end_date` (optional): End date in ISO format

**Example:**
```
GET /api/reports/trips?imei=123456789012345&start_date=2025-01-01&end_date=2025-01-07
```

**Response:**
```json
{
  "imei": "123456789012345",
  "start_date": "2025-01-01",
  "end_date": "2025-01-07",
  "trips": [
    {
      "imei": "123456789012345",
      "start_time": "2025-01-01T08:00:00",
      "end_time": "2025-01-01T09:30:00",
      "start_lat": 40.7128,
      "start_lon": -74.0060,
      "end_lat": 40.7580,
      "end_lon": -73.9855,
      "distance_km": 8.5,
      "distance_miles": 5.28,
      "avg_speed": 35.2,
      "max_speed": 65.0,
      "duration_minutes": 90
    }
  ],
  "total_trips": 1,
  "total_distance_miles": 5.28,
  "total_duration_minutes": 90
}
```

## Algorithm Details

### Parking Detection
- **Threshold**: Speed < 1 km/h for at least 5 minutes
- **Classification**: 
  - Idling: Duration < 30 minutes
  - Parked: Duration ≥ 30 minutes

### Trip Detection
- **Start**: Speed > 1 km/h after being stopped
- **End**: Speed < 1 km/h for at least 5 minutes
- **Minimum Duration**: 5 minutes
- **Distance Calculation**: Haversine formula between consecutive GPS points

### Mileage Calculation
- **Daily Aggregation**: Groups GPS points by date
- **Moving Distance**: Only counts distance when speed > 1 km/h
- **Units**: Kilometers calculated, converted to miles (1 km = 0.621371 miles)

## Error Responses
```json
{
  "error": "IMEI parameter is required"
}
```

## Data Schema

### GPS Data Table
```sql
CREATE TABLE gps_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imei TEXT,
    timestamp TEXT,
    latitude REAL,
    longitude REAL,
    speed REAL
);
```

### Additional Tables
- `trips`: Stores processed trip data
- `parking_events`: Stores parking/idling events
- `fuel_data`: Stores fuel consumption data
- `temperature_data`: Stores temperature readings

## Notes
- All timestamps are in ISO format
- Distance calculations use the Haversine formula
- Speed threshold for movement detection is 1 km/h
- Minimum event duration is 5 minutes
- Fuel and temperature reports require additional sensor data
