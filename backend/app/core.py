import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(os.getenv("JUSTICEVAULT_ROOT", os.getenv("SLIDMS_ROOT", str(Path(__file__).resolve().parents[2]))))
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    DATA_DIR = Path("/tmp/data")
else:
    DATA_DIR = ROOT / "data"
VAULT_DIR = DATA_DIR / "vault"
DB_PATH = DATA_DIR / "justicevault.db"
SECRET = os.getenv("JUSTICEVAULT_SECRET", os.getenv("SLIDMS_SECRET", "justicevault-super-secure-production-secret-key-2026")).encode()
FERNET_KEY = os.getenv("JUSTICEVAULT_FERNET_KEY")
FERNET = Fernet(FERNET_KEY.encode() if FERNET_KEY else base64.urlsafe_b64encode(hashlib.sha256(SECRET).digest()))

def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

_DB_INITIALIZED = False

def connection():
    global _DB_INITIALIZED
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    try:
        db.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    try:
        db.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    db.row_factory = sqlite3.Row
    return db

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000)
    return f"{salt}${base64.b64encode(derived).decode()}"

def check_password(password: str, encoded: str) -> bool:
    try:
        salt, _ = encoded.split("$", 1)
        return hmac.compare_digest(hash_password(password, salt), encoded)
    except Exception:
        return False

def issue_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "name": user["name"],
        "role": user["role"],
        "badge": user.get("badge", ""),
        "clearance": user.get("clearance", 3),
        "department": user.get("department", "Police"),
        "org_msp": user.get("org_msp", "PoliceHQ.Org1MSP"),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=12)).timestamp())
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def read_token(token: str) -> dict | None:
    try:
        raw, supplied = token.split(".", 1)
        if not hmac.compare_digest(hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest(), supplied):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        return payload if payload["exp"] >= int(datetime.now(timezone.utc).timestamp()) else None
    except Exception:
        return None

def init_db():
    db = connection()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        badge TEXT NOT NULL,
        clearance INTEGER NOT NULL,
        org_msp TEXT NOT NULL,
        designation TEXT NOT NULL,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cases(
        id TEXT PRIMARY KEY,
        fir_number TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        department TEXT NOT NULL,
        assigned_officer TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS documents(
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        name TEXT NOT NULL,
        document_type TEXT NOT NULL,
        department TEXT NOT NULL,
        current_version INTEGER NOT NULL,
        original_hash TEXT NOT NULL,
        current_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        is_confidential INTEGER DEFAULT 0,
        vault_path TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS document_versions(
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        case_id TEXT NOT NULL,
        version_num INTEGER NOT NULL,
        file_hash TEXT NOT NULL,
        parent_hash TEXT,
        reason TEXT NOT NULL,
        vault_path TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS victims(
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        anonymized_code TEXT NOT NULL,
        age_group TEXT NOT NULL,
        gender TEXT,
        incident_type TEXT NOT NULL,
        threat_level TEXT NOT NULL,
        is_confidential INTEGER DEFAULT 1,
        masked_payload TEXT NOT NULL,
        encrypted_payload TEXT NOT NULL,
        required_clearance INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS snapshots(
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        case_id TEXT,
        observed_hash TEXT NOT NULL,
        trusted_hash TEXT NOT NULL,
        vault_path TEXT NOT NULL,
        detected_by TEXT NOT NULL,
        detected_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        role TEXT,
        department TEXT,
        case_id TEXT,
        document_id TEXT,
        action TEXT NOT NULL,
        result TEXT NOT NULL,
        reason TEXT,
        signature_proof TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS custody(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT NOT NULL,
        case_id TEXT,
        from_user TEXT NOT NULL,
        to_user TEXT NOT NULL,
        purpose TEXT NOT NULL,
        hash TEXT NOT NULL,
        signature_ref TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS access_requests(
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL,
        approved_by TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS ledger_blocks(
        block_num INTEGER PRIMARY KEY,
        channel_id TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        data_hash TEXT NOT NULL,
        block_hash TEXT NOT NULL,
        tx_count INTEGER NOT NULL,
        endorsers TEXT NOT NULL,
        tx_payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sync_queue(
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        document_type TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        user_id TEXT NOT NULL,
        synced_at TEXT
    );
    CREATE TABLE IF NOT EXISTS esign_authorizations(
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        case_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        purpose TEXT NOT NULL,
        signature_type TEXT NOT NULL,
        signature_proof TEXT NOT NULL,
        status TEXT NOT NULL,
        auth_token TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # Migration: Ensure cases table has new required columns if upgrading
    existing_case_cols = {col["name"] for col in db.execute("PRAGMA table_info(cases)").fetchall()}
    columns_to_add = [
        ("case_type", "TEXT DEFAULT 'OTHER'"),
        ("police_station", "TEXT DEFAULT 'Cyber Crime Branch HQ'"),
        ("investigating_officer", "TEXT DEFAULT 'Inspector Vikram Rathore'"),
        ("priority", "TEXT DEFAULT 'NORMAL'"),
        ("incident_date", "TEXT"),
        ("location", "TEXT DEFAULT 'Metropolitan Jurisdiction'"),
        ("reference_number", "TEXT")
    ]
    for col_name, col_def in columns_to_add:
        if col_name not in existing_case_cols:
            try:
                db.execute(f"ALTER TABLE cases ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # Migration: Ensure documents table has classification and requires_esign columns
    existing_doc_cols = {col["name"] for col in db.execute("PRAGMA table_info(documents)").fetchall()}
    doc_cols_to_add = [
        ("classification", "TEXT DEFAULT 'UNCLASSIFIED'"),
        ("requires_esign", "INTEGER DEFAULT 0")
    ]
    for col_name, col_def in doc_cols_to_add:
        if col_name not in existing_doc_cols:
            try:
                db.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # Ensure restricted documents exist for e-Sign demo workflows
    restricted_docs = [
        ("DOC-NATSEC-001", "CASE-2026-001", "National_Security_Intercept_Transcript.pdf", "NATIONAL_SECURITY_INTERCEPT", "Intelligence", 1, "NATIONAL_SECURITY", 1, "higher.demo", b"RESTRICTED EVIDENTIARY PAYLOAD: Raw encrypted satellite communication logs intercept detailing foreign funding pipeline across offshore entities. CONFIDENTIAL UNDER SIH26190 NATIONAL SECURITY PROTOCOLS."),
        ("DOC-TOPSEC-002", "CASE-2026-014", "Top_Secret_Encrypted_Communication_Dump.json", "TOP_SECRET_SERVER_DUMP", "Cyber Intelligence", 1, "TOP_SECRET", 1, "admin.demo", b'{"protocol": "TOP_SECRET_EVIDENCE", "payload": "Encrypted VoIP server memory extraction with active cryptographic hashes and node endpoint keys.", "classification": "TOP_SECRET"}'),
        ("DOC-CONF-003", "CASE-2026-001", "Highly_Confidential_Financial_Offshore_Nodes.pdf", "HIGHLY_CONFIDENTIAL_AUDIT", "Forensic Accounting", 1, "HIGHLY_CONFIDENTIAL", 1, "higher.demo", b"CONFIDENTIAL FINANCIAL RECORD: Shell banking accounts and encrypted SWIFT transaction references linked to primary syndicate accounts.")
    ]
    for r_id, r_case, r_name, r_type, r_dept, r_ver, r_class, r_req, r_creator, r_content in restricted_docs:
        existing_doc = db.execute("SELECT id FROM documents WHERE id=?", (r_id,)).fetchone()
        if not existing_doc:
            vpath = os.path.join(VAULT_DIR, f"{r_id}_v1.enc")
            Path(vpath).write_bytes(FERNET.encrypt(r_content))
            h = hashlib.sha256(r_content).hexdigest()
            db.execute(
                "INSERT INTO documents (id, case_id, name, document_type, department, current_version, original_hash, current_hash, status, is_confidential, vault_path, created_by, created_at, classification, requires_esign) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r_id, r_case, r_name, r_type, r_dept, r_ver, h, h, "INTACT", 1, vpath, r_creator, utcnow(), r_class, r_req)
            )
            # Add version 1 entry
            db.execute(
                "INSERT INTO document_versions (id, document_id, case_id, version_num, file_hash, parent_hash, reason, vault_path, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"VER-{r_id}-V1", r_id, r_case, 1, h, None, "Original Secure Evidence Deposit", vpath, r_creator, utcnow())
            )
    db.commit()

    # Seed 5 standard SIH demo accounts + legacy accounts
    existing_user = db.execute("SELECT 1 FROM users WHERE id='police.demo'").fetchone()
    if not existing_user:
        users = [
            # 5 Core SIH Demo Roles with SIH requested usernames
            ("police.demo", "Inspector Vikram Rathore", "POLICE_OFFICER", "Police", "IND-POL-7721", 3, "PoliceHQ.Org1MSP", "Lead Investigating Officer", "Police@Demo2026!"),
            ("forensic.demo", "Dr. Priya Iyer", "FORENSIC_OFFICER", "Forensics", "CFSL-DEL-209", 4, "ForensicLab.Org2MSP", "Chief Forensic Examiner", "Forensic@Demo2026!"),
            ("judiciary.demo", "Justice R.K. Verma", "JUDGE", "Judiciary", "JUD-MAH-0012", 6, "Judiciary.Org3MSP", "Principal Sessions Judge", "Judiciary@Demo2026!"),
            ("higher.demo", "DIG Asha Rao, IPS", "HIGHER_OFFICER", "Higher Authority", "IPS-MAH-1044", 5, "PoliceHQ.Org1MSP", "Deputy Inspector General", "Higher@Demo2026!"),
            ("admin.demo", "Sanjay Deshmukh", "ADMIN", "PMO Governance", "SEC-ADM-9901", 5, "SystemAdmin.Org0MSP", "Security Node Architect & PMO", "Admin@Demo2026!"),

            # Legacy compatibility aliases
            ("io-001", "Inspector Vikram Rathore", "POLICE_OFFICER", "Police", "IND-POL-7721", 3, "PoliceHQ.Org1MSP", "Lead Investigating Officer", "demo123"),
            ("forensic-001", "Dr. Priya Iyer", "FORENSIC_OFFICER", "Forensics", "CFSL-DEL-209", 4, "ForensicLab.Org2MSP", "Chief Forensic Examiner", "demo123"),
            ("judge-001", "Justice R.K. Verma", "JUDGE", "Judiciary", "JUD-MAH-0012", 6, "Judiciary.Org3MSP", "Principal Sessions Judge", "demo123"),
            ("senior-001", "DIG Asha Rao, IPS", "HIGHER_OFFICER", "Higher Authority", "IPS-MAH-1044", 5, "PoliceHQ.Org1MSP", "Deputy Inspector General", "demo123"),
            ("admin-001", "Sanjay Deshmukh", "ADMIN", "PMO Governance", "SEC-ADM-9901", 5, "SystemAdmin.Org0MSP", "Security Node Architect & PMO", "demo123")
        ]
        for u in users:
            db.execute(
                "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?)",
                (u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], hash_password(u[8]))
            )

        # Seed Cases
        cases = [
            ("CASE-2026-001", "FIR 2026/8741", "State v. N. Sharma", "Multi-crore financial fraud, banking API manipulation, and digital evidence exfiltration.", "ACTIVE", "HIGH", "Police", "police.demo", utcnow(), "FINANCIAL_CRIME", "Cyber Crime Branch HQ", "Inspector Vikram Rathore", "HIGH", "2026-08-14", "Mumbai Central", "REF-8741"),
            ("CASE-2026-014", "FIR 2026/8122", "Operation Blue Gate", "Encrypted VoIP network intercept, cyber syndicate communications, and server forensic dumps.", "ACTIVE", "NORMAL", "Forensics", "forensic.demo", utcnow(), "CYBER_CRIME", "Special Cell Cyber Wing", "Dr. Priya Iyer", "NORMAL", "2026-08-20", "Delhi Zone 4", "REF-8122"),
            ("CASE-2026-009", "FIR 2026/7808", "Biometric Identity Theft Case", "Forged biometric authentication tokens and unauthorized government credential generation.", "PENDING_REVIEW", "ELEVATED", "Police", "police.demo", utcnow(), "FRAUD", "State Crime Investigation Dept", "Inspector Vikram Rathore", "ELEVATED", "2026-08-25", "Pune Cyber Cell", "REF-7808")
        ]
        for c in cases:
            db.execute(
                "INSERT OR REPLACE INTO cases (id, fir_number, title, description, status, risk_level, department, assigned_officer, created_at, case_type, police_station, investigating_officer, priority, incident_date, location, reference_number) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                c
            )

        # Seed Victims (Basic & Confidential Profiles)
        victims = [
            (
                "VIC-2026-001",
                "CASE-2026-001",
                "WIT-ALPHA-92",
                "25-34 Years",
                "Male",
                "Protected Whistleblower & Banking Witness",
                "GRADE A - HIGH RISK",
                1,
                json.dumps({
                    "victim_id": "VIC-2026-001",
                    "witness_code": "WIT-ALPHA-92",
                    "full_name": "S•••••• K••••",
                    "safehouse_address": "Sector ••, Confidential Safehouse #4, Mumbai",
                    "government_id": "AADHAAR ••••-••••-8821",
                    "secure_phone": "+91 98••• ••621",
                    "threat_assessment": "GRADE A - HIGH RISK",
                    "statement_digest": "Whistleblower provided encrypted memory dump containing illicit transaction ledger from offshore gateway."
                }),
                json.dumps({
                    "victim_id": "VIC-2026-001",
                    "witness_code": "WIT-ALPHA-92",
                    "full_name": "Siddharth Kulshrestha",
                    "safehouse_address": "Flat 804, Building 12-B, Sagarika Enclave, Worli Seaface, Mumbai 400018",
                    "government_id": "AADHAAR 8291-3304-8821",
                    "secure_phone": "+91 98201 44621",
                    "email": "siddharth.k.whistleblower@secure-mail.in",
                    "threat_assessment": "GRADE A - HIGH RISK",
                    "statement_digest": "Whistleblower provided full decrypted memory dump confirming illicit transaction ledger routed through Swiss-Mauritius payment hub on 14 Aug 2026."
                }),
                5,
                utcnow()
            ),
            (
                "VIC-2026-002",
                "CASE-2026-001",
                "VIC-TOX-881",
                "35-44 Years",
                "Male",
                "Key Accused Associate / Deceased Witness",
                "RESTRICTED FORENSIC",
                1,
                json.dumps({
                    "victim_id": "VIC-2026-002",
                    "witness_code": "VIC-TOX-881",
                    "full_name": "R•••• M••••",
                    "safehouse_address": "Confidential Forensic Mortuary Vault #2",
                    "government_id": "AADHAAR ••••-••••-3391",
                    "secure_phone": "Restricted Cellular Intercept",
                    "threat_assessment": "FORENSIC CASE WITNESS"
                }),
                json.dumps({
                    "victim_id": "VIC-2026-002",
                    "witness_code": "VIC-TOX-881",
                    "full_name": "Rahul Mehra (Deceased / Key Accused Associate)",
                    "safehouse_address": "Mortuary Cell 4, Central Forensic Science Laboratory, Mumbai",
                    "government_id": "AADHAAR 6610-4491-3391",
                    "secure_phone": "+91 91223 88102 (IMEI: 864402049182391)",
                    "email": "rahul.mehra.associate@offshorepay.io",
                    "threat_assessment": "CONFIRMED FORENSIC TOXICOLOGY INCIDENT - SYNTHETIC FENTANYL ANALOG DETECTED"
                }),
                4,
                utcnow()
            )
        ]
        for v in victims:
            db.execute("INSERT OR REPLACE INTO victims VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", v)

        # Genesis Block for Fabric
        genesis_block = (
            0,
            "channel-legal-evidence",
            "0000000000000000000000000000000000000000000000000000000000000000",
            hashlib.sha256(b"GENESIS_CONFIG_JUSTICEVAULT_EVIDENCE_CC_V2.1").hexdigest(),
            hashlib.sha256(b"FABRIC_CHANNEL_GENESIS_BLOCK_0").hexdigest(),
            1,
            json.dumps(["PoliceHQ.Org1MSP", "ForensicLab.Org2MSP", "Judiciary.Org3MSP"]),
            json.dumps({"tx_id": "TX-GENESIS-000000", "type": "CONFIG_UPDATE", "chaincode": "evidence_cc:v2.1", "status": "COMMITTED"}),
            utcnow()
        )
        db.execute("INSERT OR REPLACE INTO ledger_blocks VALUES (?,?,?,?,?,?,?,?,?)", genesis_block)

        # Seed initial documents into encrypted vault & database
        sample_docs = [
            ("DOC-88219", "CASE-2026-001", "FIR_2026_8741_Official.pdf", "First Information Report (FIR)", "Police", 2, b"%PDF-1.4 Official First Information Report - State v. N. Sharma - Crime Branch Investigation 2026", 0, "police.demo"),
            ("DOC-99104", "CASE-2026-001", "Forensic_Examination_Report_v2.pdf", "Forensic Analysis Report", "Forensics", 1, b"%PDF-1.4 Digital Forensics Examination Report - Memory Dump Analysis & VoIP Intercept Logs", 0, "forensic.demo"),
            ("DOC-44012", "CASE-2026-001", "Evidence_Package_Seized_Drive.zip", "Digital Forensics Evidence", "Forensics", 1, b"PK\x03\x04 Cryptographic Evidence Package - Mobile VoIP Intercepts & Seized Hash Records", 0, "police.demo"),
            ("DOC-77031", "CASE-2026-014", "Intercept_Wiretap_Transcript.pdf", "Wiretap Transcript", "Police", 1, b"%PDF-1.4 Authorized Court Wiretap Intercept Transcript - Server node 194.26.29.112", 1, "police.demo")
        ]

        prev_h = genesis_block[4]
        for idx, (d_id, c_id, name, d_type, dept, ver, raw_data, is_conf, created_by) in enumerate(sample_docs, start=1):
            digest = hashlib.sha256(raw_data).hexdigest()
            rel_path = f"{d_id}/v{ver}-original.bin"
            vpath = VAULT_DIR / rel_path
            vpath.parent.mkdir(parents=True, exist_ok=True)
            vpath.write_bytes(FERNET.encrypt(raw_data))

            db.execute(
                "INSERT OR REPLACE INTO documents (id, case_id, name, document_type, department, current_version, original_hash, current_hash, status, is_confidential, vault_path, created_by, created_at, classification, requires_esign) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (d_id, c_id, name, d_type, dept, ver, digest, digest, "INTACT", is_conf, rel_path, created_by, utcnow(), "CONFIDENTIAL" if is_conf else "UNCLASSIFIED", 1 if is_conf else 0)
            )

            # Store Version 1 in document_versions table
            db.execute(
                "INSERT OR REPLACE INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"{d_id}-V1", d_id, c_id, 1, digest, None, "Initial evidence upload & vault deposit", rel_path, created_by, utcnow())
            )

            # If version is 2, also store V2 record to illustrate version control
            if ver == 2:
                v2_data = raw_data + b"\n[AMENDMENT]: Added supplementary witness corroboration on 01 Sep 2026."
                v2_digest = hashlib.sha256(v2_data).hexdigest()
                v2_rel_path = f"{d_id}/v2-edited.bin"
                v2_vpath = VAULT_DIR / v2_rel_path
                v2_vpath.write_bytes(FERNET.encrypt(v2_data))
                db.execute(
                    "INSERT OR REPLACE INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (f"{d_id}-V2", d_id, c_id, 2, v2_digest, digest, "Added supplementary witness corroboration and offshore wire routing details", v2_rel_path, created_by, utcnow())
                )

            # Block mint
            p_bytes = json.dumps({"document_id": d_id, "name": name, "hash": digest, "version": ver}, sort_keys=True).encode()
            data_h = hashlib.sha256(p_bytes).hexdigest()
            hdr_raw = f"{prev_h}:{data_h}:{idx}:{utcnow()}".encode()
            b_hash = hashlib.sha256(hdr_raw).hexdigest()
            tx_env = {
                "tx_id": f"TX-MINT-{d_id}",
                "type": "DOCUMENT_REGISTERED",
                "channel": "channel-legal-evidence",
                "chaincode": "evidence_cc:v2.1",
                "payload": {"document_id": d_id, "name": name, "hash": digest, "version": ver},
                "endorsers": ["PoliceHQ.Org1MSP", "ForensicLab.Org2MSP"],
                "status": "VALID_COMMITTED",
                "timestamp": utcnow()
            }
            db.execute(
                "INSERT OR REPLACE INTO ledger_blocks VALUES (?,?,?,?,?,?,?,?,?)",
                (idx, "channel-legal-evidence", prev_h, data_h, b_hash, 1, json.dumps(["PoliceHQ.Org1MSP", "ForensicLab.Org2MSP"]), json.dumps(tx_env), utcnow())
            )
            prev_h = b_hash

        # Initial custody records
        db.execute(
            "INSERT OR REPLACE INTO custody(document_id, case_id, from_user, to_user, purpose, hash, signature_ref, created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("DOC-44012", "CASE-2026-001", "police.demo", "forensic.demo", "Official Laboratory Digital Examination", hashlib.sha256(b"PK\x03\x04 Cryptographic Evidence Package - Mobile VoIP Intercepts & Seized Hash Records").hexdigest(), "CUSTODY-SIG-88F901", utcnow())
        )
        db.execute(
            "INSERT OR REPLACE INTO custody(document_id, case_id, from_user, to_user, purpose, hash, signature_ref, created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("DOC-88219", "CASE-2026-001", "police.demo", "judiciary.demo", "Court Evidence Submission & Digital Handoff", hashlib.sha256(b"%PDF-1.4 Official First Information Report - State v. N. Sharma - Crime Branch Investigation 2026").hexdigest(), "CUSTODY-SIG-33A192", utcnow())
        )

        # Initial audit records
        initial_audits = [
            ("police.demo", "POLICE_OFFICER", "Police", "CASE-2026-001", "DOC-88219", "DOCUMENT_UPLOAD", "SUCCESS", "FIR deposited into vault and anchored on Fabric block #1", None),
            ("police.demo", "POLICE_OFFICER", "Police", "CASE-2026-001", "DOC-88219", "DOCUMENT_VERSION_CREATED", "SUCCESS", "Created V2 with supplementary witness corroboration", None),
            ("forensic.demo", "FORENSIC_OFFICER", "Forensics", "CASE-2026-001", "DOC-99104", "DOCUMENT_UPLOAD", "SUCCESS", "Forensic examination report deposited into vault and anchored on Fabric block #2", None),
            ("police.demo", "POLICE_OFFICER", "Police", "CASE-2026-001", "DOC-44012", "CUSTODY_TRANSFER", "SUCCESS", "Transferred physical & digital custody to CFSL Forensic Director", "CUSTODY-SIG-88F901")
        ]
        for a in initial_audits:
            db.execute(
                "INSERT INTO audits(user_id, role, department, case_id, document_id, action, result, reason, signature_proof, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], utcnow())
            )

    db.commit()
    db.close()

def audit(user: dict | None, action: str, result: str, case_id: str | None = None, document_id: str | None = None, reason: str | None = None, signature_proof: str | None = None, ip_address: str | None = None):
    db = connection()
    db.execute(
        "INSERT INTO audits(user_id, role, department, case_id, document_id, action, result, reason, signature_proof, ip_address, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            user and user.get("id"),
            user and user.get("role"),
            user and user.get("department"),
            case_id,
            document_id,
            action,
            result,
            reason,
            signature_proof,
            ip_address,
            utcnow()
        )
    )
    db.commit()
    db.close()

CASE_TYPES = [
    {"code": "CYBER_CRIME", "label": "Cyber Crime", "icon": "🖥️", "description": "Hacking, data breach, malware, API exploitation"},
    {"code": "BULLYING_HARASSMENT", "label": "Bullying / Harassment", "icon": "👥", "description": "Online stalking, threats, defamation"},
    {"code": "FRAUD", "label": "Fraud", "icon": "💳", "description": "Identity theft, forgery, social engineering scams"},
    {"code": "FINANCIAL_CRIME", "label": "Financial Crime", "icon": "💰", "description": "Money laundering, banking frauds, embezzlement"},
    {"code": "MISSING_PERSON", "label": "Missing Person", "icon": "🔍", "description": "Missing person reports and search operations"},
    {"code": "THEFT", "label": "Theft", "icon": "🔓", "description": "Burglary, larceny, stolen physical assets"},
    {"code": "ASSAULT", "label": "Assault", "icon": "🚨", "description": "Physical assault and violent incidents"},
    {"code": "SEXUAL_OFFENCE", "label": "Sexual Offence", "icon": "⚠️", "description": "Special protection & sensitive victim offenses"},
    {"code": "DRUG_RELATED", "label": "Drug Related", "icon": "🚫", "description": "Narcotics trafficking, contraband possession"},
    {"code": "ORGANIZED_CRIME", "label": "Organized Crime", "icon": "🎯", "description": "Syndicate operations, racketeering, arms"},
    {"code": "DOMESTIC_VIOLENCE", "label": "Domestic Violence", "icon": "🏠", "description": "Domestic abuse and family safety cases"},
    {"code": "CHILD_PROTECTION", "label": "Child Protection", "icon": "👶", "description": "Juvenile protection and minor safety"},
    {"code": "OTHER", "label": "Other", "icon": "📋", "description": "General legal investigation matters"}
]

VALID_CASE_CODES = {item["code"] for item in CASE_TYPES}

def generate_unique_case_id(case_type: str = "OTHER") -> str:
    """Generates unique sequentially formatted case IDs like JV-2026-0001 or JV-CC-2026-0001"""
    year = datetime.now(timezone.utc).year
    prefix_map = {
        "CYBER_CRIME": "CC",
        "BULLYING_HARASSMENT": "BH",
        "FRAUD": "FR",
        "FINANCIAL_CRIME": "FC",
        "MISSING_PERSON": "MP",
        "THEFT": "TH",
        "ASSAULT": "AS",
        "SEXUAL_OFFENCE": "SO",
        "DRUG_RELATED": "DR",
        "ORGANIZED_CRIME": "OC",
        "DOMESTIC_VIOLENCE": "DV",
        "CHILD_PROTECTION": "CP",
        "OTHER": "GEN"
    }
    type_code = prefix_map.get(case_type.upper(), "GEN")
    
    db = connection()
    count = db.execute("SELECT count(*) FROM cases").fetchone()[0]
    db.close()
    
    counter = count + 1
    # Check uniqueness
    while True:
        candidate_id = f"JV-{type_code}-{year}-{counter:04d}"
        db = connection()
        exists = db.execute("SELECT 1 FROM cases WHERE id=?", (candidate_id,)).fetchone()
        db.close()
        if not exists:
            return candidate_id
        counter += 1
