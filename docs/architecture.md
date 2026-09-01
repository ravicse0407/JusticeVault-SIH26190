# JusticeVault Technical Architecture & Mind Map

**Platform**: JUSTICEVAULT — Secure Digital Evidence & Legal Document Trust Platform  
**Smart India Hackathon 2026** | **Problem Statement**: SIH26190 | **Team**: GenX

---

## 1. High-Level Mind Map

```
                             JUSTICEVAULT
                                  |
     -----------------------------------------------------------
     |            |             |               |              |
  IDENTITY     PRIVACY       DOCUMENT       INTEGRITY        AUDIT
     |            |             |               |              |
  Fabric CA    E-Sign        AES-256-GCM     SHA-256        Append-Only
  RBAC (L1-L6) PII Masking   Offline-First   Version Tree   Chronicle
  MSP Orgs     Step-Up Auth  Cloud Storage   Tamper Alert   Fabric Proof
```

---

## 2. End-to-End Cryptographic & Verification Flow

```mermaid
sequenceDiagram
    autonumber
    actor Officer as Law Enforcement / Forensic Officer
    participant Frontend as JusticeVault Web Client (IndexedDB)
    participant API as Secure Gateway (FastAPI RBAC)
    participant Vault as Encrypted Evidence Vault (S3 / Local AES-256)
    participant DB as Relational Chronicle (PostgreSQL / SQLite)
    participant Fabric as Hyperledger Fabric (channel-legal-evidence)

    Officer->>Frontend: Select document & input metadata
    alt System is Offline
        Frontend->>Frontend: Compute client-side SHA-256 & Encrypt into IndexedDB Queue
        Frontend-->>Officer: Display "Offline — Securely Queued"
        Note over Frontend,API: Connection restored -> Trigger Sync Center
    end
    Frontend->>API: POST /api/documents (Multipart payload + metadata)
    API->>API: Verify Token, RBAC & Clearance Level
    API->>API: Calculate SHA-256 fingerprint on raw payload
    API->>Vault: Store ciphertext using StorageService (AES-256-GCM)
    API->>DB: Record document metadata, original_hash, version V1
    API->>Fabric: Invoke evidence_cc:RegisterDocument(docID, hash, creator)
    Fabric-->>API: Merkle block committed (#Tx, BlockHash, Endorser Signatures)
    API->>DB: Append immutable audit record (DOCUMENT_UPLOAD, SUCCESS)
    API-->>Frontend: HTTP 200 { status: "INTACT", block_num: 21, hash: "..." }
```

---

## 3. Version Control Invariant (Original-Preserving Architecture)

When an authorized user edits an existing investigation document:
1. **Original Version V1 is NEVER overwritten or mutated**.
2. A new version `V2` is created as an independent cryptographic entity.
3. Both versions are stored in the encrypted storage layer.
4. Database records:
   - `original_hash`: SHA-256 of V1
   - `current_hash`: SHA-256 of V2
   - `parent_hash`: Explicit cryptographic pointer from V2 to V1
   - `reason`: Justification for amendment entered by the officer.
5. Hyperledger Fabric registers `RegisterDocumentVersion` creating an immutable provenance chain: `V1 (Genesis) -> V2 (Amended) -> V3 (Reviewed)`.

---

## 4. Tamper Detection & Forensic Quarantine Protocol

```mermaid
graph TD
    A[Evidence File Requested] --> B[Retrieve Encrypted Payload from Vault]
    B --> C[Decrypt via StorageService]
    C --> D[Compute SHA-256 Fingerprint]
    D --> E{Calculated Hash == Trusted Ledger Hash?}
    E -- YES --> F[Status: DOCUMENT VERIFIED / INTACT]
    E -- NO --> G[ALERT: DOCUMENT TAMPER DETECTED]
    G --> H[Preserve Original Trusted Evidence in Vault]
    G --> I[Store Altered Copy in Quarantine Vault as SNAP-xxxx]
    G --> J[Record Tamper Incident in Audit Chronicle]
    G --> K[Commit Tamper Alert to Hyperledger Fabric]
    G --> L[Mark Active Display: UNTRUSTED / TAMPERED]
```

---

## 5. Storage Abstraction (StorageService)

To ensure zero vendor lock-in, all evidence asset operations pass through the `StorageService` interface:
- `upload_encrypted_file(document_id, version, data, suffix)`
- `download_encrypted_file(relative_path)`
- `delete_or_archive_file(relative_path)`
- `get_file_metadata(relative_path)`
- `verify_file_hash(relative_path, expected_hash)`

Implementations provided:
1. `EncryptedLocalStorage`: Authenticated encryption at-rest for local rapid deployments.
2. `S3StorageAdapter`: Production-grade adapter connecting to AWS S3, MinIO, or National Informatics Centre (NIC) Government Cloud with zero code changes.
