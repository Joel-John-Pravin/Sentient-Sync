#!/usr/bin/env python
"""
PCAP Reader - Reads PCAP/PCAPNG files and sends to cloud brain
Use this for demo instead of live Suricata
"""

import json
import time
import requests
import os
from datetime import datetime
import logging

# Try to import scapy
try:
    from scapy.all import PcapReader, IP, TCP, UDP, ICMP
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("Scapy not installed. Using mock data mode.")

# Configuration
CLOUD_API_URL = "http://localhost:5000/ingest"
LOGSTASH_URL = "http://localhost:5001"
PCAP_DIR = "C:/SentientSync/pcap_samples"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def anonymize_ip(ip):
    """Simple anonymization for demo"""
    if not ip:
        return "unknown"
    import hashlib
    return hashlib.md5(ip.encode()).hexdigest()[:10]

def process_with_scapy(pcap_file):
    """Process PCAP/PCAPNG file with Scapy using a robust reader"""
    if not SCAPY_AVAILABLE:
        return generate_mock_events()
    
    events = []
    try:
        # Use PcapReader which is better at handling different formats (like PCAPNG)
        with PcapReader(pcap_file) as pcap_reader:
            for i, pkt in enumerate(pcap_reader):
                if i >= 50:  # Limit to 50 packets for demo
                    break
                
                if IP in pkt:
                    event = {
                        'id': f"pcap_{i}_{time.time()}",
                        'timestamp': datetime.now().isoformat(),
                        'event_type': 'alert',
                        'src_ip': pkt[IP].src,
                        'dest_ip': pkt[IP].dst,
                        'proto': 'TCP' if TCP in pkt else 'UDP' if UDP in pkt else 'ICMP' if ICMP in pkt else 'IP',
                        'src_port': pkt[TCP].sport if TCP in pkt else pkt[UDP].sport if UDP in pkt else 0,
                        'dest_port': pkt[TCP].dport if TCP in pkt else pkt[UDP].dport if UDP in pkt else 0,
                        'alert': {
                            'signature': 'PCAP Replay Discovery',
                            'category': 'Network Traffic',
                            'severity': 3
                        }
                    }
                    events.append(event)
    except Exception as e:
        logger.error(f"Error reading {pcap_file}: {e}")
        logger.info("Falling back to mock data due to file error.")
        return generate_mock_events()
    
    return events

def generate_mock_events():
    """Generate mock events for demo when Scapy fails or files are missing"""
    events = []
    mock_ips = ["192.168.1.100", "10.0.0.5", "172.16.1.20", "8.8.8.8", "1.1.1.1"]
    mock_ports = [80, 443, 53, 22, 3389]
    
    for i in range(20):
        event = {
            'id': f"mock_{i}_{time.time()}",
            'timestamp': datetime.now().isoformat(),
            'event_type': 'alert',
            'src_ip': mock_ips[i % len(mock_ips)],
            'dest_ip': mock_ips[(i+2) % len(mock_ips)],
            'proto': 'TCP' if i % 3 != 0 else 'UDP',
            'src_port': mock_ports[i % len(mock_ports)],
            'dest_port': mock_ports[(i+1) % len(mock_ports)],
            'alert': {
                'signature': f'Mock Security Alert {i}',
                'category': 'simulated',
                'severity': 1
            }
        }
        events.append(event)
    
    return events

def send_to_cloud(events):
    """Send events to cloud brain"""
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
            'alert_info': event.get('alert', {})
        })
    
    try:
        logger.info(f"Sending {len(payload)} events to cloud...")
        # Note: Added a short timeout for the demo environment
        response = requests.post(CLOUD_API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Upload successful!")
            logger.info(f"Summary: {result.get('summary', {})}")
            
            # Send to Logstash
            try:
                requests.post(LOGSTASH_URL, json=result, timeout=2)
                logger.info("Sent to Logstash for visualization")
            except:
                pass
            
            return result
        else:
            logger.error(f"Server returned status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Connection Error: {e}")
    
    return None

def main():
    logger.info("="*60)
    logger.info("PCAP Reader Started - SentientSync Demo")
    logger.info("="*60)
    
    # Check if we have PCAP files
    pcap_files = []
    if os.path.exists(PCAP_DIR):
        # Look for both .pcap and .pcapng
        pcap_files = [f for f in os.listdir(PCAP_DIR) if f.endswith(('.pcap', '.pcapng'))]
    
    if pcap_files:
        logger.info(f"Found {len(pcap_files)} PCAP file(s)")
        # Process the first valid file found
        pcap_path = os.path.join(PCAP_DIR, pcap_files[0])
        logger.info(f"Processing: {pcap_files[0]}")
        events = process_with_scapy(pcap_path)
        
        if events:
            send_to_cloud(events)
    else:
        logger.info("No PCAP files found in directory. Using mock data.")
        events = generate_mock_events()
        send_to_cloud(events)
    
    logger.info("Task completed. Check your dashboard.")

if __name__ == "__main__":
    main()
