# JusticeVault REST API Reference Manual

**Platform**: JUSTICEVAULT (SIH26190 | Team GenX)  
**Base URL**: `http://127.0.0.1:8000`  
**Authentication**: Bearer JWT token header (`Authorization: Bearer <token>`)

---

## 1. System & Health

### `GET /api/health`
Returns system health, ledger channel status, and adapter mode.
- **Response `200 OK`**:
```json
{
  "status": "HEALTHY",
  "platform": "JUSTICEVAULT",
  "team": "GenX",
  "problem_id": "SIH26190",
  "ledger_channel": "channel-legal-evidence",
  "ledger_mode": "MOCK_FABRIC_ADAPTER",
  "version": "2.5.0",
  "timestamp": "2026-09-01T16:36:06+00:00"
}
```

---

## 2. Authentication & Identity

### `POST /api/auth/login`
Authenticates an officer using PBKDF2-HMAC-SHA256 verification and issues a signed JWT.
- **Request (Form Data)**:
  - `username`: `police.demo` | `forensic.demo` | `judiciary.demo` | `higher.demo` | `admin.demo`
  - `password`: `Police@Demo2026!` | etc.
- **Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "Bearer",
  "user": {
    "id": "police.demo",
    "name": "Inspector Vikram Rathore",
    "role": "POLICE_OFFICER",
    "department": "Police",
    "clearance": 3,
    "org_msp": "PoliceHQ.Org1MSP"
  },
  "ledger_status": "MOCK_FABRIC_ADAPTER"
}
```

### `GET /api/auth/me`
Returns current officer profile and active clearance credentials.

---

## 3. Case Registry

### `GET /api/cases`
Returns list of cases accessible to the authenticated officer's jurisdiction and clearance.

### `POST /api/cases`
Registers a new investigation case and anchors metadata block on Hyperledger Fabric.
- **Request (Form Data)**:
  - `case_id`: `CASE-2026-099`
  - `fir_number`: `FIR 2026/9999`
  - `title`: `Operation Falcon Eye`
  - `description`: `Cyber crime investigation...`
  - `risk_level`: `HIGH`

---

## 4. Evidence & Document Management

### `GET /api/documents`
Returns authorized documents with strict RBAC filtering:
- Police officers see police reports and FIRs.
- Forensic officers see forensic lab reports.
- Judiciary and Higher Officers see full cross-department dossiers.

### `POST /api/documents`
Uploads evidence document, computes SHA-256, encrypts via StorageService, records V1 metadata, and commits proof transaction to Fabric.
- **Request (Multipart Form Data)**:
  - `case_id`: string
  - `document_type`: `FIR` | `POLICE_REPORT` | `FORENSIC_REPORT` | `LAB_FINDINGS`
  - `name`: string
  - `is_confidential`: boolean
  - `file`: binary upload

### `POST /api/documents/{id}/versions`
Creates an amended version (V2/V3), preserving original V1 untouched.
- **Request (Multipart Form Data)**:
  - `reason`: string (Mandatory justification)
  - `file`: binary upload

### `GET /api/documents/{id}/download`
Securely decrypts and streams evidence payload with content-disposition header. Logs `DOCUMENT_DOWNLOAD` audit event.

### `GET /api/documents/{id}/verify`
Compares stored ciphertext SHA-256 against on-chain Fabric proof.

### `POST /api/documents/{id}/verify-upload`
Forensic verification and live tamper detection demo trigger.
- If uploaded file matches trusted hash -> Returns `INTACT`.
- If uploaded file differs -> Triggers `TAMPER_DETECTED`, preserves original, generates quarantine snapshot (`SNAP-xxxx`), commits tamper incident to blockchain.

---

## 5. Victim Privacy & Step-Up eSign

### `GET /api/confidential-records`
Returns zero-knowledge masked victim profiles (`Name: S•••••• K••••`).

### `POST /api/confidential-records/{id}/esign-unlock`
Executes digital eSign ceremony, verifies legal justification and step-up authorization, decrypts confidential PII, and logs unmasking audit event.
- **Request (Form Data)**:
  - `reason`: string (Court Order # / Investigation Justification)
  - `signature_passphrase`: string (`demo-sign`)

---

## 6. Offline Queue & Cloud Sync

### `POST /api/sync`
Batch synchronizes documents queued locally in IndexedDB while offline.
- Uploads encrypted assets to cloud storage.
- Validates SHA-256 integrity.
- Commits batch proof transactions to Fabric ledger.

---

## 7. Hyperledger Fabric & Audit Trail

### `GET /api/ledger/blocks`
Inspects blockchain blocks, Merkle hashes, transaction counts, and MSP endorser signatures on `channel-legal-evidence`.

### `GET /api/audits`
Returns the append-only, tamper-evident chronicle of every operational and cryptographic event across JusticeVault.
