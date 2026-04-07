
# Sentient-Sync

## Privacy-Preserving Hybrid Intrusion Detection System

**98.22% Accuracy | Privacy Protected | Free & Open Source**

## What is this?

Sentient-Sync detects cyber attacks on your network while keeping your IP addresses private.

-  **98.22% accurate** - Better than traditional systems
-  **Privacy protected** - Your IPs never leave your network
-  **Works offline** - Stores data during internet outage
-  **Free** - No cost, open source

##  Architecture
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOCAL NETWORK │
│ ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                               │
│ │ Suricata         │───▶│ SQLite           │◀───│ JSON             │                               │
│ │ IDS              │      │ Buffer           │      │ Monitor          │                              │
│ └─────────────┘      └─────────────┘      └──────┬──────┘                               │
│                                                                │                                        │
│                                                      ┌──────▼──────┐                               │
│                                                      │ SHA-256          │                               │
│                                                      │ Anonymization    │                               │
│                                                      └──────┬──────┘                               │
└────────────────────────────────────────────────┼────────────────────────────┘
					│ HTTPS
					▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CLOUD LAYER │
│ ┌─────────────┐      ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│ │ Cloud            │───▶│ Logstash         │───▶│Elasticsearch    │───▶│ Kibana          │      │
│ │ Brain            │      │ (Port 5001)      │     │ (Port 9200)      │     │ (Port 5601)     │      │
│ │ LSTM-CNN API     │      └─────────────┘     └─────────────┘     └─────────────┘      │
│ └─────────────┘                                                                                    │
└─────────────────────────────────────────────────────────────────────────────┘


##  Quick Start

### 1. Install Docker
Download from: https://docker.com

### 2. Start the system
```bash
cd dashboard
docker-compose up -d

cd ../cloud_brain
docker build -t sentient-brain .
docker run -d -p 5000:5000 sentient-brain
3. Run monitor
bash
cd sync_bridge
python json_monitor_fixed.py
4. Open dashboard
http://localhost:5601

 Results
Metric	Score
Accuracy	98.22%
Precision	98.17%
Recall	98.22%

Detects 7 types of attacks:

BENIGN (normal traffic)
DoS/DDoS attacks
Port scanning
Brute force attacks
Web attacks
Botnet activity
Rare attacks

 Project Structure

Sentient-Sync/
├── cloud_brain/          # LSTM-CNN API (Docker)
│   ├── app.py           # Flask application
│   ├── Dockerfile       # Container configuration
│   └── requirements.txt # Python dependencies
├── sync_bridge/         # Local sync manager
│   └── json_monitor_fixed.py
├── dashboard/           # ELK Stack configuration
│   ├── docker-compose.yml
│   └── logstash.conf
├── scripts/             # Utility scripts
│   ├── test_direct.py   # API testing
│   ├── pcap_reader.py   # PCAP processing
│   └── train_model.py   # Model training
└── docs/                # Documentation

Requirements

Docker Desktop
Python 3.8+
8GB RAM
20GB disk space

Authors
Joel John Pravin A | Gokula Krishnan M | Bharanidharan T
Guide: Dr. M. Umaselvi M.E Ph.d.,

Department of Computer Science and Engineering
P.A. College of Engineering and Technology, Pollachi

📄 License
MIT License - Free for everyone