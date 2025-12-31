import redis
import json
import os

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
QUEUE_NAME = 'gps_packets'

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    # Test connection
    redis_client.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except redis.ConnectionError:
    print(f"Warning: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
    redis_client = None

def push_packet(packet):
    """
    Push a GPS packet to Redis queue
    
    Args:
        packet (dict): GPS packet data containing imei, lat, lon, speed, heading, timestamp
    """
    if redis_client is None:
        print("Redis not available - skipping queue push")
        return False
    
    try:
        # Serialize packet to JSON
        packet_json = json.dumps(packet)
        # Push to Redis list (queue)
        result = redis_client.lpush(QUEUE_NAME, packet_json)
        print(f"Pushed packet to queue: {packet['imei']} at {packet['timestamp']}")
        return True
    except Exception as e:
        print(f"Error pushing packet to Redis: {e}")
        return False

def get_packet():
    """
    Get a GPS packet from Redis queue (blocking)
    
    Returns:
        dict: GPS packet data or None if no packet available
    """
    if redis_client is None:
        return None
    
    try:
        # Pop from right side of list (FIFO queue)
        result = redis_client.brpop(QUEUE_NAME, timeout=1)
        if result:
            _, packet_json = result
            packet = json.loads(packet_json)
            return packet
    except Exception as e:
        print(f"Error getting packet from Redis: {e}")
    return None

def get_queue_length():
    """
    Get the current length of the GPS packet queue
    
    Returns:
        int: Number of packets in queue
    """
    if redis_client is None:
        return 0
    
    try:
        return redis_client.llen(QUEUE_NAME)
    except Exception as e:
        print(f"Error getting queue length: {e}")
        return 0
