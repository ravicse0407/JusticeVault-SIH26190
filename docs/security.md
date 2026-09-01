# JusticeVault Security Architecture & Threat Model

**Platform**: JUSTICEVAULT (SIH26190 | Team GenX)  
**Security Principles**: Confidentiality, Integrity, Non-Repudiation, Least Privilege, Defense-in-Depth

---

## 1. Role-Based Access Control (RBAC) & Clearance Matrix

| Role | Clearance | Cases | FIR / Police Docs | Forensic Labs | Judiciary Orders | Masked Victim PII | Unmasked Confidential PII | System Governance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Police Officer** (`police.demo`) | L3 | Create / Own | Read / Write | ❌ Hidden | Read | ✅ Basic Only | ❌ (Step-up required) | ❌ |
| **Forensic Officer** (`forensic.demo`) | L4 | Assigned | ❌ Hidden | Read / Write | Read | ✅ Basic Only | ❌ | ❌ |
| **Judge** (`judiciary.demo`) | L6 | All Jurisdiction | Read | Read | Read / Write | ✅ Basic Only | ✅ Via eSign (L6) | ❌ |
| **Higher Officer** (`higher.demo`) | L5 | Oversight | Read | Read | Read | ✅ Basic Only | ✅ Via eSign (L5) | Read Logs |
| **Admin / PMO** (`admin.demo`) | L5 | Node Health | ❌ No PII | ❌ No PII | ❌ No PII | ❌ No PII | ❌ No PII | ✅ Full Governance |

---

## 2. Cryptographic Security Invariants

### 1. Hashing vs Encryption
- **SHA-256**: Used strictly as a one-way cryptographic fingerprint (digest) for integrity validation and blockchain proof anchoring.
- **AES-256-GCM / Authenticated Fernet**: Used for data encryption at rest. Keys are managed exclusively server-side and never exposed to the client.

### 2. Password & Key Derivation
- Passwords stored using **PBKDF2-HMAC-SHA256** with 310,000 iterations and unique 128-bit cryptographic salts.
- Session tokens are signed using HMAC-SHA256 with timed expiration.

### 3. Hyperledger Fabric Provenance Layer
- Blockchain stores ONLY metadata, hashes, creator identities, and version links.
- No bulky documents or unencrypted personal data are ever placed on the distributed ledger.

---

## 3. Victim Privacy & Zero-Knowledge Masking

Victim and witness information is compartmentalized into two distinct tiers:
1. **Basic Profile (Public / Operational)**:
   - Anonymized witness code (e.g. `WIT-ALPHA-92`)
   - Age category (e.g. `25-34 Years`)
   - Threat risk assessment level
2. **Confidential Profile (High-Risk PII)**:
   - Full Legal Name: `█████████`
   - Phone Number: `█████████`
   - Residential Address: `Restricted`
   - Identity Proofs (Aadhaar, Passport): `Restricted`

**Step-Up eSign Requirement**: To unmask PII, the user must possess Clearance Level 5+, provide a verifiable legal justification (e.g. Court Order #), and sign an HMAC authorization challenge. Every access is logged immutably to the audit log and blockchain.

---

## 4. Screenshot & Data Leak Deterrence

In compliance with realistic cybersecurity standards, browser-based applications cannot physically block OS-level hardware screen grabs. JusticeVault provides comprehensive deterrence and auditing:
- Dynamic screen watermarks displaying `Officer Name`, `Badge #`, `IP Address`, and `UTC Timestamp`.
- Right-click context menus disabled inside sensitive document viewers.
- Browser print stylesheets automatically redact sensitive evidentiary bodies.
- Short-lived signed download tokens preventing direct URL scraping.
- Warning banners: `"CONFIDENTIAL EVIDENCE — ACCESS & VIEWING STRICTLY MONITORED"`.
