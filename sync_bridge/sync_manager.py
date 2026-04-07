#!/usr/bin/env python
"""
Sentient-Sync: Connectivity Manager & Sync Bridge
This script monitors internet connectivity and uploads local events to cloud.
"""

import sqlite3
import hashlib
import json
import time
import requests
import os
from datetime import datetime
import logging

# ==================== CONFIGURATION ====================
LOCAL_DB_PATH = "C:/Program Files/Suricata/logs/local_events.db"
CLOUD_API_URL = "http://localhost:5000/ingest"  # Our Docker cloud brain
CHECK_INTERVAL = 60  # Check every 60 seconds
SALT = b"sentient-sync-project-2025"  # For IP anonymization
BATCH_SIZE = 50  # Upload 50 events at a time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== FUNCTIONS ====================

def check_internet():
    """Check if internet is available by pinging Cloudflare DNS"""
    try:
        requests.get("https://1.1.1.1", timeout=5)
        return True
    except requests.ConnectionError:
        return False
    except Exception as e:
        logger.error(f"Internet check error: {e}")
        return False

def anonymize_ip(ip_address):
    """Hash IP addresses to preserve privacy"""
    if not ip_address or ip_address == "unknown":
        return None
    
    # Create a SHA-256 hash with salt
    hash_object = hashlib.sha256(SALT + ip_address.encode())
    # Return first 16 characters of hex digest
    return hash_object.hexdigest()[:16]

def get_unsynced_events():
    """Fetch events that haven't been synced yet"""
    if not os.path.exists(LOCAL_DB_PATH):
        logger.error(f"Database not found: {LOCAL_DB_PATH}")
        return []
    
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row  # This lets us access columns by name
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, src_ip, dest_ip, event_type, proto, alert_message
            FROM events 
            WHERE synced = 0 
            ORDER BY id 
            LIMIT ?
        """, (BATCH_SIZE,))
        
        rows = cursor.fetchall()
        conn.close()
        
        logger.info(f"Found {len(rows)} unsynced events")
        return rows
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return []

def prepare_payload(events):
    """Convert events to upload format with anonymized IPs"""
    payload = []
    
    for event in events:
        # Convert Row object to dictionary
        event_dict = dict(event)
        
        # Anonymize IPs (privacy protection!)
        event_dict['src_ip_anon'] = anonymize_ip(event_dict.get('src_ip'))
        event_dict['dest_ip_anon'] = anonymize_ip(event_dict.get('dest_ip'))
        
        # Remove original IPs
        del event_dict['src_ip']
        del event_dict['dest_ip']
        
        # Add processing metadata
        event_dict['synced_at'] = datetime.now().isoformat()
        event_dict['sync_version'] = "1.0"
        
        payload.append(event_dict)
    
    return payload

def upload_to_cloud(payload):
    """Send data to cloud brain API"""
    if not payload:
        logger.info("No data to upload")
        return []
    
    try:
        logger.info(f"Uploading {len(payload)} events to cloud...")
        
        response = requests.post(
            CLOUD_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Upload successful! Cloud response: {result}")
            
            # Extract successfully processed IDs
            processed_ids = []
            if 'analyzed_events' in result:
                for item in result['analyzed_events']:
                    if 'original_id' in item:
                        processed_ids.append(item['original_id'])
            
            return processed_ids
        else:
            logger.error(f"Upload failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
            
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to cloud API. Is Docker running?")
        return []
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return []

def mark_as_synced(event_ids):
    """Update database to mark events as synced"""
    if not event_ids:
        return
    
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        
        # Create placeholders for IN clause
        placeholders = ','.join(['?' for _ in event_ids])
        cursor.execute(f"""
            UPDATE events 
            SET synced = 1, synced_time = ? 
            WHERE id IN ({placeholders})
        """, [datetime.now().isoformat()] + event_ids)
        
        conn.commit()
        logger.info(f"Marked {cursor.rowcount} events as synced in database")
        conn.close()
        
    except sqlite3.Error as e:
        logger.error(f"Error marking events as synced: {e}")

def insert_test_event():
    """FOR TESTING: Insert a dummy event if database is empty"""
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        
        # Check if table is empty
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Inserting test event...")
            cursor.execute("""
                INSERT INTO events (timestamp, src_ip, dest_ip, event_type, proto, alert_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                "192.168.1.100",
                "8.8.8.8",
                "alert",
                "TCP",
                "Test alert: Potential port scan detected"
            ))
            conn.commit()
            logger.info("Test event inserted")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error inserting test event: {e}")

# ==================== MAIN LOOP ====================

def main():
    """Main sync loop"""
    logger.info("=" * 60)
    logger.info("Sentient-Sync Bridge Started")
    logger.info("=" * 60)
    logger.info(f"Monitoring database: {LOCAL_DB_PATH}")
    logger.info(f"Cloud API endpoint: {CLOUD_API_URL}")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
    logger.info("=" * 60)
    
    # Insert test event for demonstration
    insert_test_event()
    
    offline_mode = False
    
    while True:
        try:
            # Check internet connectivity
            if check_internet():
                if offline_mode:
                    logger.info("Internet connection restored! Syncing...")
                    offline_mode = False
                
                # Get unsynced events
                events = get_unsynced_events()
                
                if events:
                    # Prepare payload (anonymize IPs)
                    payload = prepare_payload(events)
                    
                    # Upload to cloud
                    synced_ids = upload_to_cloud(payload)
                    
                    # Mark as synced
                    if synced_ids:
                        mark_as_synced(synced_ids)
                else:
                    logger.info("No new events to sync")
            
            else:
                if not offline_mode:
                    logger.info("No internet connection. Operating in offline mode.")
                    offline_mode = True
                else:
                    logger.debug("Still offline, buffering data locally...")
            
            # Wait before next check
            logger.info(f"Waiting {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Shutting down by user request...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(CHECK_INTERVAL)
    
    logger.info("Sync Bridge stopped.")

if __name__ == "__main__":
    main()
