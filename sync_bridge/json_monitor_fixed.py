#!/usr/bin/env python
"""
JSON Monitor - Reads Suricata's eve.json and sends to cloud
No emoji version for Windows compatibility
"""

import json
import os
import time
import hashlib
import requests
from datetime import datetime
import logging

# ==================== CONFIGURATION ====================
EVE_JSON_PATH = "C:/Program Files/Suricata/logs/eve.json"
PROCESSED_LOG_PATH = "C:/SentientSync/sync_bridge/processed_events.json"
CLOUD_API_URL = "http://localhost:5000/ingest"
LOGSTASH_URL = "http://localhost:5001"  # Logstash endpoint
CHECK_INTERVAL = 10  # Check every 10 seconds
SALT = b"sentient-sync-project-2025"

# Setup logging - NO EMOJIS!
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('json_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def anonymize_ip(ip_address):
    """Hash IP addresses for privacy"""
    if not ip_address or ip_address == "unknown":
        return None
    hash_object = hashlib.sha256(SALT + str(ip_address).encode())
    return hash_object.hexdigest()[:16]

def get_processed_ids():
    """Load list of already processed event IDs"""
    if os.path.exists(PROCESSED_LOG_PATH):
        try:
            with open(PROCESSED_LOG_PATH, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_processed_ids(processed_ids):
    """Save processed event IDs to file"""
    with open(PROCESSED_LOG_PATH, 'w') as f:
        json.dump(list(processed_ids), f)

def read_new_events():
    """Read new events from eve.json that haven't been processed"""
    if not os.path.exists(EVE_JSON_PATH):
        logger.warning(f"eve.json not found at {EVE_JSON_PATH}")
        return []
    
    # Get already processed IDs
    processed_ids = get_processed_ids()
    new_events = []
    new_ids = []
    
    try:
        # Read eve.json line by line (each line is a JSON object)
        with open(EVE_JSON_PATH, 'r') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    event = json.loads(line)
                    
                    # Create unique ID for this event
                    event_str = f"{event.get('timestamp', '')}_{line_num}"
                    event_id = hashlib.md5(event_str.encode()).hexdigest()
                    
                    # Check if already processed
                    if event_id not in processed_ids:
                        # Extract relevant fields for our project
                        simplified_event = {
                            'id': event_id,
                            'timestamp': event.get('timestamp', datetime.now().isoformat()),
                            'event_type': event.get('event_type', 'unknown'),
                            'src_ip': event.get('src_ip', 'unknown'),
                            'dest_ip': event.get('dest_ip', 'unknown'),
                            'src_port': event.get('src_port', 0),
                            'dest_port': event.get('dest_port', 0),
                            'proto': event.get('proto', 'unknown'),
                        }
                        
                        # Add alert details if it's an alert event
                        if event.get('event_type') == 'alert' and 'alert' in event:
                            simplified_event['alert'] = {
                                'action': event['alert'].get('action', ''),
                                'signature': event['alert'].get('signature', ''),
                                'category': event['alert'].get('category', ''),
                                'severity': event['alert'].get('severity', 0)
                            }
                        
                        # Add HTTP details if it's HTTP traffic
                        if event.get('event_type') == 'http' and 'http' in event:
                            simplified_event['http'] = {
                                'hostname': event['http'].get('hostname', ''),
                                'url': event['http'].get('url', ''),
                                'method': event['http'].get('http_method', '')
                            }
                        
                        new_events.append(simplified_event)
                        new_ids.append(event_id)
                        
                except json.JSONDecodeError as e:
                    logger.debug(f"Skipping invalid JSON line: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error reading eve.json: {e}")
        return []
    
    # Save new IDs as processed
    if new_ids:
        processed_ids.update(new_ids)
        save_processed_ids(processed_ids)
        logger.info(f"Found {len(new_ids)} new events")
    
    return new_events

def upload_to_cloud(events):
    """Upload events to cloud brain and return the analysis results"""
    if not events:
        return None
    
    # Prepare payload with anonymized IPs
    payload = []
    for event in events:
        payload.append({
            'original_id': event['id'],
            'timestamp': event['timestamp'],
            'src_ip_anon': anonymize_ip(event.get('src_ip')),
            'dest_ip_anon': anonymize_ip(event.get('dest_ip')),
            'src_port': event.get('src_port', 0),
            'dest_port': event.get('dest_port', 0),
            'event_type': event['event_type'],
            'proto': event.get('proto', 'unknown'),
            'alert_info': event.get('alert', {}),
            'http_info': event.get('http', {})
        })
    
    try:
        logger.info(f"Uploading {len(payload)} events to cloud...")
        response = requests.post(CLOUD_API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Upload successful!")
            logger.info(f"   Summary: {result.get('summary', {})}")
            
            # Send the FULL analyzed results to Logstash
            upload_to_logstash(result)
            
            return result
        else:
            logger.error(f"Upload failed: {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to cloud API. Is Docker running?")
        return None
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None

def upload_to_logstash(analyzed_results):
    """Send the COMPLETE analyzed results to Logstash for visualization"""
    if not analyzed_results:
        return
    
    try:
        # analyzed_results should be the full response from cloud brain
        # which contains analyzed_events with verdict, confidence, etc.
        event_count = len(analyzed_results.get('analyzed_events', []))
        logger.info(f"Sending {event_count} analyzed events to Logstash for visualization")
        
        response = requests.post(
            LOGSTASH_URL,
            json=analyzed_results,  # Send the FULL analyzed response
            timeout=2
        )
        if response.status_code == 200:
            logger.debug(f"Successfully sent to Logstash")
        else:
            logger.debug(f"Logstash response: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        logger.debug("Logstash not ready yet (this is OK if starting up)")
    except Exception as e:
        logger.debug(f"Logstash upload error (non-critical): {e}")

def check_suricata_running():
    """Check if Suricata is creating logs"""
    if os.path.exists(EVE_JSON_PATH):
        # Get file size
        file_size = os.path.getsize(EVE_JSON_PATH)
        
        if file_size > 0:
            logger.info(f"Suricata log file exists with size: {file_size} bytes")
            # Don't warn about modification time - it's old data
            return True
        else:
            logger.warning("eve.json exists but is empty")
            return False
    else:
        logger.warning("eve.json not found - Suricata may not be running")
        return False

def main():
    """Main monitoring loop"""
    logger.info("=" * 60)
    logger.info("JSON Monitor Started (with Logstash integration)")
    logger.info("=" * 60)
    logger.info(f"Watching: {EVE_JSON_PATH}")
    logger.info(f"Cloud API: {CLOUD_API_URL}")
    logger.info(f"Logstash: {LOGSTASH_URL}")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
    logger.info("=" * 60)
    
    # Initial check
    check_suricata_running()
    
    while True:
        try:
            # Check for new events
            new_events = read_new_events()
            
            if new_events:
                # Upload to cloud and get analysis results
                analysis_results = upload_to_cloud(new_events)
                
                # Note: upload_to_logstash is now called INSIDE upload_to_cloud
                # to ensure we send the FULL analyzed results with verdicts
            else:
                logger.debug("No new events found")
            
            # Check Suricata status periodically (every 60 seconds)
            if int(time.time()) % 60 < CHECK_INTERVAL:
                check_suricata_running()
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
