import json
import time
import requests
from datetime import datetime

# Test event
test_event = {
    "timestamp": datetime.now().isoformat(),
    "event_type": "alert",
    "src_ip": "192.168.1.100",
    "dest_ip": "8.8.8.8",
    "proto": "TCP",
    "alert": {
        "signature": "Test Alert",
        "category": "Test",
        "severity": 1
    }
}

# Save to a test file
with open("test_event.json", "w") as f:
    json.dump(test_event, f)
print("Test event created")

try:
    # Send directly to cloud brain
    response = requests.post(
        "http://localhost:5000/ingest",
        json=[{
            'original_id': 'test123',
            'timestamp': test_event['timestamp'],
            'src_ip_anon': 'test_src_hash',
            'dest_ip_anon': 'test_dst_hash',
            'event_type': test_event['event_type'],
            'proto': test_event['proto'],
            'alert_info': test_event.get('alert', {})
        }]
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Cloud brain response: {data}")
        
        # Small delay to prevent the "Remote end closed connection" error
        time.sleep(0.5)

        # Send to logstash
        print("Attempting to send to Logstash...")
        response2 = requests.post(
            "http://localhost:5001",
            json=data,
            timeout=5 # Added timeout to prevent hanging
        )
        print(f"Sent to Logstash! Status: {response2.status_code}")
    else:
        print(f"Cloud brain failed with status: {response.status_code}")

except requests.exceptions.ConnectionError as e:
    print(f"Connection Error: Could not connect to the server. Is Logstash (5001) or Cloud Brain (5000) running?")
    print(f"Details: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
