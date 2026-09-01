# 🏛️ JUSTICEVAULT
### Secure Digital Evidence & Legal Document Trust Platform
**Smart India Hackathon 2026** | **Problem Statement**: SIH26190  
**Problem Domain**: *"Secure Digital Document Management System for Legal and Investigation Documents"*  
**Team**: **GenX**

---

<div align="center">

![JusticeVault](https://img.shields.io/badge/JusticeVault-SIH26190-blue?style=for-the-badge&logo=shield&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-2.5-green?style=for-the-badge&logo=fastapi)
![Hyperledger](https://img.shields.io/badge/Hyperledger-Fabric%202.5-orange?style=for-the-badge&logo=hyperledger)
![Python](https://img.shields.io/badge/Python-3.12+-blue?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge)

</div>

---

## 📌 Executive Summary

> **JusticeVault is NOT just another document management system.**  
> It is an **integrity-first, privacy-aware, offline-capable document trust layer** designed to preserve evidentiary chain-of-custody, enforce role-based selective disclosure, protect vulnerable victim identities with zero-knowledge E-Sign authorization, and provide immutable cryptographic provenance anchored to Hyperledger Fabric.

JusticeVault operates as a modular, high-trust security layer that interfaces seamlessly with law enforcement, forensic laboratories, and the judiciary — without replacing existing national infrastructure (CCTNS, eCourts, ICJS).

---

## ✨ Core Features

| Feature | Description |
| :--- | :--- |
| 🔐 **AES-256 Encryption at Rest** | All evidence encrypted with Fernet/AES-GCM before vault storage |
| 🛡️ **SHA-256 Tamper Detection** | Live hash mismatch detection, original preservation & quarantine |
| 🔒 **Mandatory Prototype E-Sign** | Zero-Trust authorization ceremony for National Security / Top Secret documents |
| 👁️ **Zero-Knowledge Victim Privacy** | PII masked by default; clearance-gated unmasking with digital signature |
| ⛓️ **Hyperledger Fabric Ledger** | Immutable Merkle block commits on `channel-legal-evidence` (3-Org MSP) |
| 📶 **Offline-First Architecture** | IndexedDB local queue + background sync-to-vault reconciliation |
| 📝 **Immutable Version Control** | V1 is NEVER overwritten; version chains with cryptographic parent pointers |
| 👥 **5-Role RBAC System** | Police → Forensic → Judge → Higher Officer → Admin (Clearance L3–L6) |
| 📜 **Append-Only Audit Chronicle** | Every action recorded with WHO, WHEN, WHY, HOW + Fabric block proof |
| 🏗️ **Multi-MSP Identity (X.509)** | Per-org Fabric CA credentials (`PoliceHQ.Org1MSP`, `ForensicLab.Org2MSP`, `Judiciary.Org3MSP`) |

---

## 🔑 Demo Accounts & Credentials

| Role | Username | Password | Clearance | MSP Organization |
| :--- | :--- | :--- | :--- | :--- |
| 👮 **Police Officer** | `police.demo` | `Police@Demo2026!` | L3 | `PoliceHQ.Org1MSP` |
| 🔬 **Forensic Officer** | `forensic.demo` | `Forensic@Demo2026!` | L4 | `ForensicLab.Org2MSP` |
| ⚖️ **Judiciary / Judge** | `judiciary.demo` | `Judiciary@Demo2026!` | L6 (Supreme) | `Judiciary.Org3MSP` |
| 🛡️ **Higher Police Officer** | `higher.demo` | `Higher@Demo2026!` | L5 | `PoliceHQ.Org1MSP` |
| 💻 **Admin / PMO** | `admin.demo` | `Admin@Demo2026!` | L5 | `SystemAdmin.Org0MSP` |

> **Prototype E-Sign Passphrase**: `demo-sign` or `123456`  
> All passwords are hashed with **PBKDF2-HMAC-SHA256** (310,000 iterations).

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- `pip`

### 1. Clone & Install

```bash
git clone https://github.com/<your-username>/JusticeVault-SIH26190.git
cd JusticeVault-SIH26190

cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Start Server

```bash
# From project root:
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### 3. Open Application

| URL | Description |
| :--- | :--- |
| [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | **Interactive Web App** |
| [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | **Swagger OpenAPI Docs** |
| [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) | **System Health Check** |

### 4. Run Test Suites

```bash
# From project root:

# Mandatory Prototype E-Sign Enforcement
python backend/test_esign_enforcement.py

# 14-endpoint integration tests
python backend/test_api.py

# Full multi-role SIH demo flow
python backend/test_phase6_demo.py
```

---

## 🔒 Mandatory Prototype E-Sign Authorization

For every document classified as `NATIONAL_SECURITY`, `TOP_SECRET`, or `HIGHLY_CONFIDENTIAL`:

```
User selects restricted document
        ↓
Backend checks classification (API-enforced, not UI-only)
        ↓
HTTP 403 Forbidden — Document content BLOCKED
        ↓
User clicks "🔒 Request Prototype E-Sign"
        ↓
Prototype E-Sign ceremony modal
  → Enter official purpose/justification
  → Select certificate type (DSC_TOKEN / AADHAAR_OTP / HARDWARE_HSM)
  → Enter secure PIN (demo-sign)
        ↓
Backend validates role (JUDGE / HIGHER_OFFICER / ADMIN only)
        ↓
Generates: Authorization ID • Signature Proof • 15-min Session Token
        ↓
Mints Hyperledger Fabric block + records AUDIT event
        ↓
Document content decrypted & served for authorized session
```

**Role restrictions:**
- ✅ Judiciary (Judge), Higher Officer, Admin: May perform E-Sign
- ❌ Police Officer, Forensic Officer: Cannot access or unmask National Security documents

---

## 🏗️ Architecture Overview

```
JUSTICEVAULT (SIH26190)
│
├── frontend/
│   └── index.html              # Single-page web app (Vanilla JS + CSS)
│
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI routes & business logic
│   │   └── core.py             # DB schema, encryption, ledger, init
│   ├── requirements.txt
│   └── test_*.py               # Automated test suites
│
├── blockchain/
│   └── chaincode/              # Go chaincode for Hyperledger Fabric
│
├── data/                       # Runtime data (gitignored)
│   ├── justicevault.db         # SQLite database
│   └── vault/                  # Encrypted document vault (*.enc)
│
└── docker-compose.yml          # Multi-container Docker deployment
```

### Hyperledger Fabric Network Topology

```
                    HYPERLEDGER FABRIC (v2.5)
                               |
                     channel-legal-evidence
                               |
         -------------------------------------------------
         |                     |                         |
     Police MSP           Forensic MSP            Judiciary MSP
  (PoliceHQ.Org1MSP)  (ForensicLab.Org2MSP)  (Judiciary.Org3MSP)
         |                     |                         |
       Peer                  Peer                      Peer
  (peer0.police:7051)  (peer0.forensic:8051)  (peer0.judiciary:9051)
```

---

## 🛡️ Security Architecture

| Component | Prototype Implementation | Production Target |
| :--- | :--- | :--- |
| **Evidence Encryption** | AES-256-GCM (Fernet) at rest | HSM / AWS KMS / NIC Key Vault |
| **Integrity Hashing** | Full SHA-256 on binary streams | SHA-256 / SHA-3 + NIC PKI timestamp |
| **Tamper Detection** | Live hash mismatch + quarantine | SOC SIEM alerts + forensic sandbox |
| **Victim Privacy** | Zero-knowledge masked JSON | DPDP Act 2023 / Section 327 CrPC |
| **Digital E-Sign** | HMAC-SHA256 ceremony simulation | C-DAC eSign / Aadhaar eSign / DSC X.509 |
| **Offline Sync** | Browser IndexedDB + API sync | PWA Service Worker Sync |
| **Blockchain** | MockBlockchainService + real Go chaincode | 3-Org Hyperledger Fabric 2.5 Consortium |
| **Authentication** | JWT Bearer + PBKDF2-HMAC-SHA256 | Aadhaar OTP / MFA / SSO |

---

## 🎯 SIH Demo Sequence (5–7 Minutes)

1. **Police Officer** → Register case, upload FIR, inspect SHA-256 fingerprint
2. **Offline Mode** → Queue document locally → Switch online → Watch auto-sync to vault + Fabric block
3. **Version Control** → Edit FIR → V1 preserved immutably → V2 minted with parent pointer
4. **Forensic Officer** → Upload lab report, run hash integrity check, trigger tamper simulation
5. **Judiciary (Judge)** → Prototype E-Sign ceremony → Decrypt National Security document → Victim PII unmask
6. **Admin / PMO** → Explore Hyperledger Fabric topology, SOC security quarantine, cloud KMS settings

---

## 🔮 Future Integrations

1. **DigiLocker** — Direct citizen evidence deposit and verified document retrieval
2. **CCTNS / ICJS** — Sync with India's Inter-operable Criminal Justice System
3. **C-DAC Aadhaar eSign** — Government-approved biometric digital signatures
4. **Forensic Mobile App** — Air-gapped crime scene evidence capture with GPS attestation
5. **NIC MeghRaj Cloud** — Government cloud storage deployment

---

## 📋 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Role-based login → JWT token |
| `GET` | `/api/dashboard` | Role-specific dashboard data |
| `POST` | `/api/cases` | Create new case (CASE-XXXX) |
| `GET` | `/api/cases` | List cases with role filtering |
| `POST` | `/api/documents/upload` | Upload & encrypt evidence document |
| `GET` | `/api/documents` | List documents (restricted hidden for Police/Forensic) |
| `POST` | `/api/documents/{id}/esign-authorize` | 🔒 Prototype E-Sign ceremony |
| `GET` | `/api/documents/{id}/download` | Download (E-Sign enforced for restricted) |
| `GET` | `/api/documents/{id}/preview` | Preview (E-Sign enforced for restricted) |
| `GET` | `/api/esign-authorizations` | List E-Sign authorization chronicle |
| `GET` | `/api/audits` | Append-only audit chronicle |
| `GET` | `/api/ledger/blocks` | Hyperledger Fabric block explorer |
| `POST` | `/api/sync` | Offline queue sync-to-vault |
| `GET` | `/api/health` | System health check |

---

## 📦 Docker Deployment

```bash
docker compose up -d --build
```

App accessible at: `http://localhost:8000`

---

*Developed by **Team GenX** for **Smart India Hackathon 2026** — Problem Statement SIH26190.*  
*JusticeVault: Because evidence integrity is the foundation of justice.*
