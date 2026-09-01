# JusticeVault Deployment & Operations Guide

**Platform**: JUSTICEVAULT (SIH26190 | Team GenX)

---

## 1. Quick Local Execution (Zero-Dependency SQLite Mode)

### Prerequisites
- Python 3.10+
- Web browser (Chrome / Edge / Firefox)

### Step 1: Initialize Virtual Environment
```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

### Step 2: Start Backend Server
```powershell
uvicorn app.main:app --reload --port 8000
```

### Step 3: Access Web Application
- **Interactive UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 2. Docker & Multi-Container Deployment

```bash
# Bring up JusticeVault API, PostgreSQL, MinIO S3, and Frontend
docker compose up -d --build

# View container logs
docker compose logs -f justicevault-backend
```

---

## 3. Real Hyperledger Fabric Production Integration

When connecting to an active Hyperledger Fabric 2.5+ peer network:

1. Deploy the chaincode using `./blockchain/network/network.sh deployCC`.
2. Configure `.env`:
```env
BLOCKCHAIN_MODE=FABRIC_REAL
FABRIC_CHANNEL=channel-legal-evidence
FABRIC_CONNECTION_PROFILE=./blockchain/network/connection-profile.json
FABRIC_CA_URL=https://ca.justicevault.gov.in:7054
FABRIC_USER_CERT=./crypto/police_admin.crt
FABRIC_USER_KEY=./crypto/police_admin.key
```
3. Restart JusticeVault service. The status indicator on the dashboard will switch from `BLOCKCHAIN: MOCK MODE` to `BLOCKCHAIN: FABRIC CONNECTED`.
