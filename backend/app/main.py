import base64
import datetime
import hashlib
import json
import uuid
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from .core import (
    ROOT, CASE_TYPES, VALID_CASE_CODES, audit, check_password,
    connection, generate_unique_case_id, init_db, issue_token, read_token, utcnow
)
from .services import ledger, secure_read, secure_store, sha256

app = FastAPI(
    title="JUSTICEVAULT — Secure Digital Evidence & Legal Document Trust Platform",
    description="SIH 2026 Problem Statement SIH26190 | Team GenX",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {
        "status": "HEALTHY",
        "platform": "JUSTICEVAULT",
        "team": "GenX",
        "problem_id": "SIH26190",
        "ledger_channel": "channel-legal-evidence",
        "ledger_mode": "MOCK_FABRIC_ADAPTER",
        "version": "2.5.0",
        "timestamp": utcnow()
    }

def current_user(authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ") if authorization else ""
    claims = read_token(token)
    if not claims:
        raise HTTPException(401, "Authentication required. Please sign in to JusticeVault.")
    db = connection()
    row = db.execute(
        "SELECT id, name, role, department, badge, clearance, org_msp, designation FROM users WHERE id=?",
        (claims["sub"],)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(401, "Unknown or deactivated officer identity.")
    return dict(row)

def require_clearance(min_clearance: int):
    def check(user=Depends(current_user)):
        if user["clearance"] < min_clearance:
            audit(user, "CLEARANCE_CHECK", "DENIED", reason=f"Requires clearance L{min_clearance}, user is L{user['clearance']}")
            raise HTTPException(403, f"Insufficient security clearance. Level {min_clearance} required.")
        return user
    return check

# ================= AUTHENTICATION =================

@app.post("/api/auth/login")
def login(request: Request, username: str = Form(), password: str = Form()):
    client_ip = request.client.host if request.client else "127.0.0.1"
    db = connection()
    row = db.execute("SELECT * FROM users WHERE id=?", (username,)).fetchone()
    db.close()

    if not row or not check_password(password, row["password_hash"]):
        audit(None, "LOGIN", "DENIED", reason=f"Invalid credentials for user '{username}'", ip_address=client_ip)
        raise HTTPException(401, "Invalid officer ID or passphrase.")

    user = dict(row)
    del user["password_hash"]
    token = issue_token(user)
    audit(user, "LOGIN", "SUCCESS", reason=f"Authenticated as {user['role']} ({user['department']}, Clearance L{user['clearance']})", ip_address=client_ip)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": user,
        "ledger_status": "MOCK_FABRIC_ADAPTER"
    }

@app.get("/api/auth/me")
def get_current_profile(user=Depends(current_user)):
    return user

# ================= DASHBOARDS & OVERVIEW =================

@app.get("/api/dashboard")
def get_dashboard(user=Depends(current_user)):
    db = connection()
    total_cases = db.execute("SELECT count(*) FROM cases").fetchone()[0]
    total_docs = db.execute("SELECT count(*) FROM documents").fetchone()[0]
    tamper_alerts = db.execute("SELECT count(*) FROM documents WHERE status='TAMPERED'").fetchone()[0]
    blocks_count = db.execute("SELECT count(*) FROM ledger_blocks").fetchone()[0]
    recent_audits = [dict(x) for x in db.execute("SELECT * FROM audits ORDER BY id DESC LIMIT 10").fetchall()]
    recent_blocks = [dict(x) for x in db.execute("SELECT block_num, channel_id, block_hash, tx_count, endorsers, created_at FROM ledger_blocks ORDER BY block_num DESC LIMIT 6").fetchall()]
    db.close()

    # Parse endorsers JSON
    for b in recent_blocks:
        try:
            b["endorsers"] = json.loads(b["endorsers"])
        except Exception:
            pass

    return {
        "total_cases": total_cases,
        "documents": total_docs,
        "tamper_alerts": tamper_alerts,
        "fabric_blocks": blocks_count,
        "recent_blocks": recent_blocks,
        "audits": recent_audits,
        "officer": user,
        "blockchain_mode": "MOCK_FABRIC_ADAPTER"
    }

# ================= CASE REGISTRY =================

def normalize_case_type(raw_type: str | None) -> str:
    if not raw_type:
        return "OTHER"
    clean = str(raw_type).strip().upper().replace(" ", "_").replace("/", "_").replace("-", "_")
    alias_map = {
        "CYBER": "CYBER_CRIME",
        "CYBER_CRIME": "CYBER_CRIME",
        "BULLYING": "BULLYING_HARASSMENT",
        "BULLYING_HARASSMENT": "BULLYING_HARASSMENT",
        "FRAUD": "FRAUD",
        "FINANCIAL": "FINANCIAL_CRIME",
        "FINANCIAL_CRIME": "FINANCIAL_CRIME",
        "MISSING": "MISSING_PERSON",
        "MISSING_PERSON": "MISSING_PERSON",
        "THEFT": "THEFT",
        "ASSAULT": "ASSAULT",
        "SEXUAL": "SEXUAL_OFFENCE",
        "SEXUAL_OFFENCE": "SEXUAL_OFFENCE",
        "DRUG": "DRUG_RELATED",
        "DRUG_RELATED": "DRUG_RELATED",
        "ORGANISED": "ORGANIZED_CRIME",
        "ORGANIZED": "ORGANIZED_CRIME",
        "ORGANIZED_CRIME": "ORGANIZED_CRIME",
        "DOMESTIC": "DOMESTIC_VIOLENCE",
        "DOMESTIC_VIOLENCE": "DOMESTIC_VIOLENCE",
        "CHILD": "CHILD_PROTECTION",
        "CHILD_PROTECTION": "CHILD_PROTECTION",
        "OTHER": "OTHER"
    }
    return alias_map.get(clean, "OTHER")

@app.get("/api/cases")
def list_cases(user=Depends(current_user)):
    db = connection()
    rows = [dict(x) for x in db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()]
    db.close()
    return rows

@app.post("/api/cases")
async def create_case(request: Request, user=Depends(current_user)):
    if user["role"] == "FORENSIC_OFFICER":
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Forensic officers are not authorized to create case records."
                }
            }
        )

    # Support JSON, Form-data, and URL-encoded body
    content_type = request.headers.get("content-type", "")
    body = {}
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            body = {}

    case_title = str(body.get("caseTitle") or body.get("title") or "").strip()
    raw_case_type = body.get("caseType") or body.get("case_type") or ("OTHER" if "title" in body and "caseTitle" not in body and "caseType" not in body else "")
    police_station = str(body.get("policeStation") or body.get("police_station") or ("Cyber Crime Branch HQ" if "title" in body and "caseTitle" not in body else "")).strip()
    investigating_officer = str(body.get("investigatingOfficer") or body.get("investigating_officer") or (user["name"] if "title" in body and "caseTitle" not in body else "")).strip()
    priority = str(body.get("priority") or body.get("risk_level") or "NORMAL").strip().upper()
    description = str(body.get("description") or "").strip()
    incident_date = str(body.get("incidentDate") or body.get("incident_date") or "").strip()
    location = str(body.get("location") or "").strip()
    reference_number = str(body.get("referenceNumber") or body.get("reference_number") or body.get("fir_number") or "").strip()
    requested_id = str(body.get("case_id") or body.get("caseId") or "").strip()

    # Enforce field validations
    field_errors = {}
    if not case_title or len(case_title) < 2:
        field_errors["caseTitle"] = "Case title is required (minimum 2 characters)"
    if not raw_case_type:
        field_errors["caseType"] = "Case type is required"
    if not police_station:
        field_errors["policeStation"] = "Police station is required"
    if not investigating_officer:
        field_errors["investigatingOfficer"] = "Investigating officer is required"
    if not priority:
        field_errors["priority"] = "Priority is required"
    if not description or len(description) < 5:
        field_errors["description"] = "Description is required (minimum 5 characters)"

    if field_errors:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Please correct the highlighted fields: " + "; ".join(field_errors.values()),
                    "fields": field_errors
                }
            }
        )

    case_type = normalize_case_type(raw_case_type)
    case_id = requested_id if requested_id else generate_unique_case_id(case_type)
    fir_number = reference_number if reference_number else f"FIR/{utcnow()[:4]}/{case_id.split('-')[-1]}"
    created_at = utcnow()

    db = connection()
    try:
        db.execute(
            """INSERT OR REPLACE INTO cases (
                id, fir_number, title, description, status, risk_level, department, assigned_officer, created_at,
                case_type, police_station, investigating_officer, priority, incident_date, location, reference_number
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                case_id, fir_number, case_title, description, "ACTIVE", priority, user["department"], user["id"], created_at,
                case_type, police_station, investigating_officer, priority, incident_date, location, reference_number
            )
        )
        db.commit()
    except Exception as e:
        db.close()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Unable to create case: {str(e)}"
                }
            }
        )
    db.close()

    # Record case creation provenance on Hyperledger Fabric ledger (mock mode)
    ledger_receipt = ledger.record("CASE_REGISTERED", {
        "case_id": case_id,
        "fir_number": fir_number,
        "case_type": case_type,
        "lead_officer": investigating_officer,
        "department": user["department"],
        "org": user["org_msp"]
    }, [user["org_msp"], "Judiciary.Org3MSP"])

    # Create audit event: CASE_CREATED
    audit(
        user,
        "CASE_CREATED",
        "SUCCESS",
        case_id=case_id,
        reason=f"Case {case_id} registered with FIR {fir_number}. Category: {case_type}. Fabric Block #{ledger_receipt['block_num']}"
    )

    return {
        "success": True,
        "status": "SUCCESS",
        "case_id": case_id,
        "message": "✓ CASE CREATED SUCCESSFULLY",
        "data": {
            "case_id": case_id,
            "case_type": case_type,
            "caseTitle": case_title,
            "title": case_title,
            "fir_number": fir_number,
            "created_by": user["name"],
            "assigned_officer": user["id"],
            "investigating_officer": investigating_officer,
            "police_station": police_station,
            "priority": priority,
            "description": description,
            "created_at": created_at,
            "status": "ACTIVE",
            "blockchain_mode": "MOCK_FABRIC_ADAPTER",
            "blockchain_message": "BLOCKCHAIN: MOCK MODE",
            "ledger": ledger_receipt
        },
        "ledger": ledger_receipt
    }

@app.get("/api/cases/{case_id}")
def get_case_details(case_id: str, user=Depends(current_user)):
    db = connection()
    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(404, f"Case '{case_id}' not found.")

    docs = [dict(x) for x in db.execute("SELECT * FROM documents WHERE case_id=? ORDER BY created_at DESC", (case_id,)).fetchall()]
    victims = [dict(x) for x in db.execute("SELECT id, anonymized_code, age_group, incident_type, threat_level, required_clearance FROM victims WHERE case_id=?", (case_id,)).fetchall()]
    audits = [dict(x) for x in db.execute("SELECT * FROM audits WHERE case_id=? ORDER BY id DESC LIMIT 20", (case_id,)).fetchall()]
    db.close()

    res = dict(case)
    res["documents"] = docs
    res["victims"] = victims
    res["audits"] = audits
    return res

# ================= EVIDENCE DOCUMENTS & SELECTIVE DISCLOSURE =================

@app.get("/api/documents")
def list_documents(case_id: str | None = None, user=Depends(current_user)):
    db = connection()
    # Departmental selective disclosure rules:
    # - POLICE cannot see internal confidential Forensics notes unless shared
    # - FORENSICS cannot see internal confidential Police reports unless shared
    # - JUDICIARY, HIGHER_OFFICER, and ADMIN have holistic cross-departmental authorized view
    if case_id:
        rows = [dict(x) for x in db.execute("SELECT * FROM documents WHERE case_id=? ORDER BY created_at DESC", (case_id,)).fetchall()]
    else:
        rows = [dict(x) for x in db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()]
    db.close()

    # Filter by selective disclosure:
    # - POLICE and FORENSICS cannot view RESTRICTED (NATIONAL_SECURITY, TOP_SECRET, HIGHLY_CONFIDENTIAL) documents
    # - POLICE cannot see internal confidential Forensics notes unless shared
    # - FORENSICS cannot see internal confidential Police reports unless shared
    # - JUDICIARY, HIGHER_OFFICER, and ADMIN have holistic authorized oversight
    accessible = []
    for d in rows:
        is_restricted = (d.get("requires_esign") == 1 or d.get("classification") in ("NATIONAL_SECURITY", "TOP_SECRET", "HIGHLY_CONFIDENTIAL"))
        if user["role"] in ("POLICE_OFFICER", "FORENSIC_OFFICER"):
            if is_restricted:
                continue
            if user["role"] == "POLICE_OFFICER" and d["department"] == "Forensics" and d.get("is_confidential") == 1:
                continue
            if user["role"] == "FORENSIC_OFFICER" and d["department"] == "Police" and d.get("is_confidential") == 1:
                continue
            accessible.append(d)
        else:
            accessible.append(d)

    return accessible

@app.post("/api/documents")
async def upload_document(
    case_id: str = Form(),
    document_type: str = Form(),
    is_confidential: int = Form(0),
    file: UploadFile = File(),
    user=Depends(current_user)
):
    db = connection()
    case = db.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(404, f"Case '{case_id}' not found.")

    data = await file.read()
    document_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    digest = sha256(data)
    vault_path = secure_store(document_id, 1, data, suffix="original")

    db.execute(
        "INSERT INTO documents (id, case_id, name, document_type, department, current_version, original_hash, current_hash, status, is_confidential, vault_path, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (document_id, case_id, file.filename, document_type, user["department"], 1, digest, digest, "INTACT", is_confidential, vault_path, user["id"], utcnow())
    )

    # Record Version 1 in document_versions table (Original is immutable)
    db.execute(
        "INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"{document_id}-V1", document_id, case_id, 1, digest, None, "Initial evidence upload & vault deposit", vault_path, user["id"], utcnow())
    )

    db.commit()
    db.close()

    # Fabric Block Commit
    ledger_receipt = ledger.record("DOCUMENT_REGISTERED", {
        "document_id": document_id,
        "case_id": case_id,
        "filename": file.filename,
        "document_type": document_type,
        "department": user["department"],
        "sha256_fingerprint": digest,
        "version": 1,
        "uploaded_by": user["id"],
        "org_msp": user["org_msp"]
    }, [user["org_msp"], "ForensicLab.Org2MSP"])

    audit(user, "DOCUMENT_UPLOAD", "SUCCESS", case_id=case_id, document_id=document_id, reason=f"Fingerprint: {digest[:16]}... Block: #{ledger_receipt['block_num']}")

    return {
        "document_id": document_id,
        "filename": file.filename,
        "sha256": digest,
        "version": 1,
        "status": "INTACT",
        "ledger": ledger_receipt
    }

# ================= VERSION CONTROL (ORIGINAL PRESERVATION) =================

@app.post("/api/documents/{document_id}/versions")
async def create_document_version(
    document_id: str,
    reason: str = Form(),
    file: UploadFile = File(),
    user=Depends(current_user)
):
    """
    Creates a new version (V2, V3, etc.) while preserving the original V1 completely untouched.
    """
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found in vault.")

    data = await file.read()
    new_version_num = doc["current_version"] + 1
    new_digest = sha256(data)
    parent_digest = doc["current_hash"]

    # Store new version in encrypted vault separately
    v_path = secure_store(document_id, new_version_num, data, suffix=f"v{new_version_num}")

    version_id = f"{document_id}-V{new_version_num}"
    db.execute(
        "INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (version_id, document_id, doc["case_id"], new_version_num, new_digest, parent_digest, reason, v_path, user["id"], utcnow())
    )

    # Update document pointer
    db.execute(
        "UPDATE documents SET current_version=?, current_hash=?, status='INTACT' WHERE id=?",
        (new_version_num, new_digest, document_id)
    )
    db.commit()
    db.close()

    # Commit version proof to Hyperledger Fabric
    ledger_receipt = ledger.record("DOCUMENT_VERSION_CREATED", {
        "document_id": document_id,
        "version": new_version_num,
        "new_hash": new_digest,
        "parent_hash": parent_digest,
        "reason": reason,
        "created_by": user["id"]
    }, [user["org_msp"], "Judiciary.Org3MSP"])

    audit(
        user,
        "DOCUMENT_VERSION_CREATED",
        "SUCCESS",
        case_id=doc["case_id"],
        document_id=document_id,
        reason=f"Created V{new_version_num}: {reason}. Fabric Block #{ledger_receipt['block_num']}"
    )

    return {
        "status": "VERSION_CREATED",
        "document_id": document_id,
        "version": new_version_num,
        "new_hash": new_digest,
        "parent_hash": parent_digest,
        "reason": reason,
        "ledger": ledger_receipt
    }

@app.get("/api/documents/{document_id}/versions")
def get_document_versions(document_id: str, user=Depends(current_user)):
    db = connection()
    versions = [dict(x) for x in db.execute("SELECT * FROM document_versions WHERE document_id=? ORDER BY version_num ASC", (document_id,)).fetchall()]
    db.close()
    return versions

# ================= RESTRICTED PROTOTYPE E-SIGN & EVIDENCE ACCESS =================

@app.post("/api/documents/{document_id}/esign-authorize")
async def esign_authorize_document(document_id: str, request: Request, user=Depends(current_user)):
    """
    PROTOTYPE E-SIGN: Mandatory step-up digital signature verification for NATIONAL_SECURITY,
    TOP_SECRET, and HIGHLY_CONFIDENTIAL documents.
    Generates temporary authorization token and ledger-backed audit proof.
    """
    if user["role"] in ("POLICE_OFFICER", "FORENSIC_OFFICER"):
        raise HTTPException(403, "Access Denied: Police and Forensic Officers cannot authorize restricted National Security dossiers.")

    try:
        body = await request.json()
    except Exception:
        body = {}

    passphrase = body.get("passphrase") or body.get("pin") or ""
    purpose = body.get("purpose") or body.get("reason") or ""
    signature_type = body.get("signature_type") or "DSC_TOKEN"

    if len(purpose.strip()) < 4:
        raise HTTPException(422, "Access purpose / official justification is mandatory (minimum 4 characters).")

    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, f"Document '{document_id}' not found.")

    if passphrase not in ("demo-sign", "123456"):
        # Log rejected authorization attempt
        auth_id = f"ESIGN-REJ-{uuid.uuid4().hex[:8].upper()}"
        db.execute(
            "INSERT INTO esign_authorizations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (auth_id, user["id"], user["role"], doc["case_id"], document_id, purpose, signature_type, "INVALID_PIN", "REJECTED", "NONE", utcnow(), utcnow())
        )
        db.commit()
        db.close()
        audit(user, "ESIGN_REJECTED", "FAILURE", case_id=doc["case_id"], document_id=document_id, reason=f"Rejected E-Sign attempt for {doc['name']}: Invalid PIN")
        raise HTTPException(403, "PROTOTYPE E-SIGN REJECTED: Invalid digital signature PIN / Passphrase.")

    # Generate valid temporary authorization session token
    auth_id = f"ESIGN-AUTH-{uuid.uuid4().hex[:8].upper()}"
    auth_token = f"jwt-esign-{uuid.uuid4().hex}"
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
    proof = f"ESIGN-SHA256-{sha256((user['id'] + document_id + purpose + utcnow()).encode('utf-8'))[:24]}"

    db.execute(
        "INSERT INTO esign_authorizations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (auth_id, user["id"], user["role"], doc["case_id"], document_id, purpose, signature_type, proof, "VERIFIED", auth_token, expires_at, utcnow())
    )
    db.commit()
    db.close()

    # Record Fabric Block
    ledger_receipt = ledger.record("CONFIDENTIAL_DOCUMENT_ESIGN_AUTHORIZED", {
        "authorization_id": auth_id,
        "document_id": document_id,
        "case_id": doc["case_id"],
        "officer": user["id"],
        "role": user["role"],
        "classification": doc["classification"] if "classification" in doc.keys() else "RESTRICTED",
        "purpose": purpose,
        "proof": proof,
        "expires_at": expires_at
    }, [user["org_msp"], "Judiciary.Org3MSP"])

    audit(user, "CONFIDENTIAL_DOCUMENT_ESIGN_GRANTED", "SUCCESS", case_id=doc["case_id"], document_id=document_id, reason=f"E-Sign {auth_id} granted by {user['role']}. Purpose: {purpose}. Block #{ledger_receipt['block_num']}")

    return {
        "success": True,
        "authorization_id": auth_id,
        "auth_token": auth_token,
        "document_id": document_id,
        "document_name": doc["name"],
        "classification": doc["classification"] if "classification" in doc.keys() else "RESTRICTED",
        "status": "VERIFIED",
        "expires_at": expires_at,
        "signature_proof": proof,
        "prototype_notice": "PROTOTYPE E-SIGN: Not legally equivalent to India's statutory DSC service",
        "ledger": ledger_receipt
    }

@app.get("/api/esign-authorizations")
def get_esign_authorizations(user=Depends(current_user)):
    db = connection()
    now_iso = utcnow()
    rows = [dict(x) for x in db.execute("SELECT * FROM esign_authorizations ORDER BY created_at DESC").fetchall()]
    for r in rows:
        if r["status"] == "VERIFIED" and r["expires_at"] < now_iso:
            r["status"] = "EXPIRED"
            db.execute("UPDATE esign_authorizations SET status='EXPIRED' WHERE id=?", (r["id"],))
    db.commit()
    db.close()
    return rows

@app.get("/api/documents/{document_id}/download")
def download_document(document_id: str, request: Request, user=Depends(current_user)):
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found in vault.")

    is_restricted = (doc["requires_esign"] == 1 if "requires_esign" in doc.keys() else False) or (doc["classification"] in ("NATIONAL_SECURITY", "TOP_SECRET", "HIGHLY_CONFIDENTIAL") if "classification" in doc.keys() else False)
    if is_restricted:
        esign_token = request.headers.get("X-Esign-Auth-Token") or request.query_params.get("esign_token") or request.query_params.get("esign_auth_token")
        if not esign_token:
            db.close()
            audit(user, "RESTRICTED_ACCESS_BLOCKED", "DENIED", case_id=doc["case_id"], document_id=document_id, reason=f"Blocked attempt to access {doc['name']} without mandatory E-Sign token")
            raise HTTPException(403, "PROTOTYPE E-SIGN REQUIRED: E-Sign authorization is mandatory before document content can be viewed or downloaded.")

        auth = db.execute(
            "SELECT * FROM esign_authorizations WHERE user_id=? AND document_id=? AND auth_token=? AND status='VERIFIED'",
            (user["id"], document_id, esign_token)
        ).fetchone()
        now_iso = utcnow()
        if not auth or auth["expires_at"] < now_iso:
            if auth and auth["expires_at"] < now_iso:
                db.execute("UPDATE esign_authorizations SET status='EXPIRED' WHERE id=?", (auth["id"],))
                db.commit()
            db.close()
            audit(user, "ESIGN_AUTH_EXPIRED_OR_INVALID", "DENIED", case_id=doc["case_id"], document_id=document_id, reason=f"E-Sign token expired/invalid for {doc['name']}")
            raise HTTPException(403, "PROTOTYPE E-SIGN EXPIRED OR INVALID: Please request a new E-Sign authorization session.")

    try:
        data = secure_read(doc["vault_path"])
    except Exception as e:
        db.close()
        raise HTTPException(500, f"Vault decryption error: {str(e)}")

    audit(user, "DOCUMENT_DOWNLOAD", "SUCCESS", case_id=doc["case_id"], document_id=document_id, reason=f"Downloaded {doc['name']}")
    db.close()

    media_type = "application/octet-stream"
    name_lower = doc["name"].lower()
    if name_lower.endswith(".pdf"):
        media_type = "application/pdf"
    elif name_lower.endswith(".json"):
        media_type = "application/json"
    elif name_lower.endswith(".txt"):
        media_type = "text/plain"
    elif name_lower.endswith((".png", ".jpg", ".jpeg")):
        media_type = "image/png"
    elif name_lower.endswith(".zip"):
        media_type = "application/zip"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{doc["name"]}"'}
    )

@app.get("/api/documents/{document_id}/preview")
def preview_document(document_id: str, request: Request, user=Depends(current_user)):
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found in vault.")

    is_restricted = (doc["requires_esign"] == 1 if "requires_esign" in doc.keys() else False) or (doc["classification"] in ("NATIONAL_SECURITY", "TOP_SECRET", "HIGHLY_CONFIDENTIAL") if "classification" in doc.keys() else False)
    if is_restricted:
        esign_token = request.headers.get("X-Esign-Auth-Token") or request.query_params.get("esign_token") or request.query_params.get("esign_auth_token")
        if not esign_token:
            db.close()
            audit(user, "RESTRICTED_ACCESS_BLOCKED", "DENIED", case_id=doc["case_id"], document_id=document_id, reason=f"Blocked attempt to preview {doc['name']} without mandatory E-Sign token")
            raise HTTPException(403, "PROTOTYPE E-SIGN REQUIRED: E-Sign authorization is mandatory before document content can be previewed.")

        auth = db.execute(
            "SELECT * FROM esign_authorizations WHERE user_id=? AND document_id=? AND auth_token=? AND status='VERIFIED'",
            (user["id"], document_id, esign_token)
        ).fetchone()
        now_iso = utcnow()
        if not auth or auth["expires_at"] < now_iso:
            if auth and auth["expires_at"] < now_iso:
                db.execute("UPDATE esign_authorizations SET status='EXPIRED' WHERE id=?", (auth["id"],))
                db.commit()
            db.close()
            raise HTTPException(403, "PROTOTYPE E-SIGN EXPIRED OR INVALID: Please request a new E-Sign authorization session.")

    try:
        data = secure_read(doc["vault_path"])
    except Exception as e:
        db.close()
        raise HTTPException(500, f"Vault decryption error: {str(e)}")

    db.close()
    return {
        "document_id": doc["id"],
        "name": doc["name"],
        "classification": doc["classification"] if "classification" in doc.keys() else "UNCLASSIFIED",
        "size_bytes": len(data),
        "content_text": data.decode("utf-8", errors="ignore")[:4000],
        "is_restricted": is_restricted
    }

@app.get("/api/documents/{document_id}/versions/{version_num}/download")
def download_document_version(document_id: str, version_num: int, user=Depends(current_user)):
    db = connection()
    v = db.execute("SELECT * FROM document_versions WHERE document_id=? AND version_num=?", (document_id, version_num)).fetchone()
    if not v:
        db.close()
        raise HTTPException(404, f"Version {version_num} of document {document_id} not found.")

    try:
        data = secure_read(v["vault_path"])
    except Exception as e:
        db.close()
        raise HTTPException(500, f"Vault decryption error: {str(e)}")

    audit(user, "VERSION_DOWNLOAD", "SUCCESS", case_id=v["case_id"], document_id=document_id, reason=f"Downloaded version V{version_num}")
    db.close()

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{document_id}_v{version_num}.bin"'}
    )

# ================= INTEGRITY LAB & FORENSIC TAMPER DETECTION =================

@app.get("/api/documents/{document_id}/verify")
def verify_document(document_id: str, user=Depends(current_user)):
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found in vault index.")

    try:
        data = secure_read(doc["vault_path"])
        observed = sha256(data)
    except Exception as e:
        db.close()
        raise HTTPException(500, f"Vault storage error: {str(e)}")

    db.close()
    is_intact = (observed == doc["original_hash"])

    audit(
        user,
        "DOCUMENT_VERIFY",
        "SUCCESS" if is_intact else "TAMPERED",
        case_id=doc["case_id"],
        document_id=document_id,
        reason=f"Observed: {observed[:16]}... vs Original: {doc['original_hash'][:16]}..."
    )

    return {
        "document_id": document_id,
        "filename": doc["name"],
        "original_hash": doc["original_hash"],
        "observed_hash": observed,
        "integrity": "INTACT" if is_intact else "TAMPERED",
        "blockchain_verified": True
    }

@app.post("/api/documents/{document_id}/verify-upload")
async def verify_uploaded_file(document_id: str, file: UploadFile = File(), user=Depends(current_user)):
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found.")

    data = await file.read()
    observed = sha256(data)

    if observed == doc["original_hash"]:
        db.close()
        audit(user, "DOCUMENT_VERIFY", "MATCH", case_id=doc["case_id"], document_id=document_id, reason="Uploaded version perfectly matches trusted original.")
        return {
            "integrity": "INTACT",
            "original_hash": doc["original_hash"],
            "observed_hash": observed,
            "message": "File integrity fully confirmed against trusted Hyperledger baseline."
        }

    # Tamper Detected: Preserve quarantined snapshot without altering original vault
    snapshot_id = f"SNAP-{uuid.uuid4().hex[:10].upper()}"
    snap_path = secure_store(document_id, doc["current_version"], data, suffix=f"tamper-{snapshot_id}")

    db.execute(
        "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?)",
        (snapshot_id, document_id, doc["case_id"], observed, doc["original_hash"], snap_path, user["id"], utcnow())
    )
    db.execute("UPDATE documents SET status='TAMPERED', current_hash=? WHERE id=?", (observed, document_id))
    db.commit()
    db.close()

    # Fabric Block Commit for Tamper Incident
    ledger_receipt = ledger.record("TAMPER_INCIDENT_COMMITTED", {
        "document_id": document_id,
        "case_id": doc["case_id"],
        "trusted_original_hash": doc["original_hash"],
        "observed_tampered_hash": observed,
        "quarantine_snapshot_id": snapshot_id,
        "status": "UNTRUSTED / TAMPERED",
        "detected_by": user["id"]
    }, [user["org_msp"], "Judiciary.Org3MSP"])

    audit(
        user,
        "TAMPER_DETECTED",
        "CRITICAL_ALERT",
        case_id=doc["case_id"],
        document_id=document_id,
        reason=f"Mismatch! Snapshot {snapshot_id} quarantined. Fabric Block #{ledger_receipt['block_num']}"
    )

    return {
        "integrity": "TAMPERED",
        "status": "UNTRUSTED / TAMPERED",
        "original_hash": doc["original_hash"],
        "observed_hash": observed,
        "snapshot_id": snapshot_id,
        "ledger": ledger_receipt,
        "warning": "Integrity mismatch detected. Original evidence in vault remains untouched; quarantined forensic snapshot created."
    }

@app.get("/api/snapshots/{snapshot_id}/download")
def download_snapshot(snapshot_id: str, user=Depends(current_user)):
    db = connection()
    snap = db.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
    if not snap:
        db.close()
        raise HTTPException(404, "Quarantine snapshot not found.")

    try:
        data = secure_read(snap["vault_path"])
    except Exception as e:
        db.close()
        raise HTTPException(500, f"Vault decryption error: {str(e)}")

    audit(user, "SNAPSHOT_DOWNLOAD", "SUCCESS", document_id=snap["document_id"], reason=f"Forensic export of quarantine snapshot {snapshot_id}")
    db.close()

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{snapshot_id}_quarantine.bin"'}
    )

# ================= VICTIM PRIVACY & ZERO-KNOWLEDGE eSIGN =================

@app.get("/api/victims")
def list_victims(user=Depends(current_user)):
    db = connection()
    rows = db.execute("SELECT id, case_id, anonymized_code, age_group, gender, incident_type, threat_level, masked_payload, required_clearance FROM victims").fetchall()
    db.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "case_id": r["case_id"],
            "anonymized_code": r["anonymized_code"],
            "age_group": r["age_group"],
            "gender": r["gender"],
            "incident_type": r["incident_type"],
            "threat_level": r["threat_level"],
            "masked_data": json.loads(r["masked_payload"]),
            "required_clearance": r["required_clearance"],
            "is_eligible": user["clearance"] >= r["required_clearance"]
        })
    return result

@app.get("/api/victims/{victim_id}/basic")
def get_victim_basic_profile(victim_id: str, user=Depends(current_user)):
    db = connection()
    v = db.execute("SELECT id, case_id, anonymized_code, age_group, gender, incident_type, threat_level FROM victims WHERE id=?", (victim_id,)).fetchone()
    db.close()
    if not v:
        raise HTTPException(404, "Victim record not found.")
    return dict(v)

@app.get("/api/victims/{victim_id}/confidential")
def get_victim_confidential_profile(victim_id: str, user=Depends(current_user)):
    db = connection()
    v = db.execute("SELECT id, case_id, anonymized_code, masked_payload, required_clearance FROM victims WHERE id=?", (victim_id,)).fetchone()
    db.close()
    if not v:
        raise HTTPException(404, "Victim record not found.")

    return {
        "id": v["id"],
        "case_id": v["case_id"],
        "anonymized_code": v["anonymized_code"],
        "status": "MASKED_RESTRICTED",
        "masked_data": json.loads(v["masked_payload"]),
        "required_clearance": v["required_clearance"],
        "notice": "Confidential PII is zero-knowledge masked by default. Digital eSign authorization required to decrypt."
    }

@app.post("/api/victims/{victim_id}/esign-authorize")
def esign_authorize_victim_pii(
    victim_id: str,
    certificate_type: str = Form("DSC_TOKEN"),
    passphrase: str = Form(),
    reason: str = Form("Official Judicial/Investigation Review"),
    user=Depends(current_user)
):
    if passphrase != "demo-sign":
        audit(user, "ESIGN_CEREMONY", "REJECTED", reason="Invalid cryptographic PIN / Passphrase")
        raise HTTPException(403, "Cryptographic eSign rejected. Valid passphrase required (use 'demo-sign').")

    db = connection()
    victim = db.execute("SELECT * FROM victims WHERE id=?", (victim_id,)).fetchone()
    db.close()

    if not victim:
        raise HTTPException(404, "Victim record not found.")

    if user["clearance"] < victim["required_clearance"]:
        audit(user, "CONFIDENTIAL_UNMASK_REQUEST", "DENIED", reason=f"Clearance L{user['clearance']} below required L{victim['required_clearance']}")
        raise HTTPException(403, f"Access Denied: Record requires clearance level {victim['required_clearance']}.")

    # Generate verifiable eSign digital proof
    signature_nonce = uuid.uuid4().hex[:12].upper()
    proof_data = f"{user['id']}:{user['badge']}:{victim_id}:{certificate_type}:{signature_nonce}:{utcnow()}".encode()
    signature_proof = f"ESIGN-SHA256-{hashlib.sha256(proof_data).hexdigest()}"

    # Record eSign transaction on Hyperledger Fabric
    ledger_receipt = ledger.record("CONFIDENTIAL_PII_UNMASKED_ESIGN", {
        "victim_id": victim_id,
        "case_id": victim["case_id"],
        "unmasked_by": user["id"],
        "badge": user["badge"],
        "role": user["role"],
        "certificate_type": certificate_type,
        "signature_proof": signature_proof,
        "purpose": reason
    }, [user["org_msp"], "Judiciary.Org3MSP"])

    audit(
        user,
        "CONFIDENTIAL_UNMASK_ESIGN",
        "GRANTED",
        case_id=victim["case_id"],
        reason=f"Decrypted via {certificate_type}. Purpose: {reason}",
        signature_proof=signature_proof
    )

    decrypted_data = json.loads(victim["encrypted_payload"])

    return {
        "victim_id": victim_id,
        "case_id": victim["case_id"],
        "status": "DECRYPTED_ACCESS_GRANTED",
        "decrypted_data": decrypted_data,
        "esign_certificate": {
            "signature_proof": signature_proof,
            "certificate_type": certificate_type,
            "officer_name": user["name"],
            "badge_number": user["badge"],
            "clearance_level": user["clearance"],
            "timestamp": utcnow(),
            "ledger_block": ledger_receipt["block_num"],
            "ledger_tx_id": ledger_receipt["tx_id"]
        }
    }

# Legacy alias for confidential records
@app.get("/api/confidential-records")
def list_confidential_records(user=Depends(current_user)):
    return list_victims(user)

@app.post("/api/confidential-records/{record_id}/esign-unlock")
def esign_unlock_confidential_alias(
    record_id: str,
    certificate_type: str = Form("DSC_TOKEN"),
    passphrase: str = Form(),
    reason: str = Form("Official Judicial/Investigation Review"),
    user=Depends(current_user)
):
    return esign_authorize_victim_pii(record_id, certificate_type, passphrase, reason, user)

# ================= OFFLINE-FIRST SYNC HUB =================

@app.post("/api/sync")
async def sync_offline_queue(payload: list[dict], user=Depends(current_user)):
    """
    Receives an array of queued offline document records, securely commits them to vault,
    verifies SHA-256 fingerprints, and mints blockchain blocks.
    """
    synced_results = []

    for item in payload:
        case_id = item.get("case_id", "CASE-2026-001")
        doc_type = item.get("document_type", "Offline Evidence Report")
        filename = item.get("filename", f"offline_doc_{uuid.uuid4().hex[:6]}.pdf")
        content_b64 = item.get("content_base64", "")

        try:
            raw_bytes = base64.b64decode(content_b64) if content_b64 else b"Offline Deposited Document Payload"
        except Exception:
            raw_bytes = b"Offline Deposited Document Payload"

        digest = sha256(raw_bytes)
        doc_id = f"DOC-OFFLINE-{uuid.uuid4().hex[:8].upper()}"
        vault_path = secure_store(doc_id, 1, raw_bytes, suffix="offline-synced")

        db = connection()
        db.execute(
            "INSERT INTO documents (id, case_id, name, document_type, department, current_version, original_hash, current_hash, status, is_confidential, vault_path, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, case_id, filename, doc_type, user["department"], 1, digest, digest, "INTACT", 0, vault_path, user["id"], utcnow())
        )
        db.execute(
            "INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"{doc_id}-V1", doc_id, case_id, 1, digest, None, "Synced from local offline queue", vault_path, user["id"], utcnow())
        )
        db.commit()
        db.close()

        ledger_receipt = ledger.record("OFFLINE_QUEUE_SYNCED", {
            "document_id": doc_id,
            "case_id": case_id,
            "filename": filename,
            "sha256": digest,
            "synced_by": user["id"]
        }, [user["org_msp"], "ForensicLab.Org2MSP"])

        audit(user, "CLOUD_SYNC", "SUCCESS", case_id=case_id, document_id=doc_id, reason=f"Synced offline file {filename}")

        synced_results.append({
            "queue_id": item.get("queue_id"),
            "document_id": doc_id,
            "filename": filename,
            "hash": digest,
            "status": "SYNCED & VERIFIED",
            "ledger_block": ledger_receipt["block_num"]
        })

    return {"status": "SUCCESS", "synced_count": len(synced_results), "items": synced_results}

# ================= HYPERLEDGER FABRIC EXPLORER =================

@app.get("/api/ledger/blocks")
def list_fabric_blocks(user=Depends(current_user)):
    db = connection()
    blocks = [dict(x) for x in db.execute("SELECT block_num, channel_id, prev_hash, data_hash, block_hash, tx_count, endorsers, created_at FROM ledger_blocks ORDER BY block_num DESC").fetchall()]
    db.close()

    for b in blocks:
        try:
            b["endorsers"] = json.loads(b["endorsers"])
        except Exception:
            pass

    return {
        "channel": "channel-legal-evidence",
        "chaincode": "evidence_cc:v2.1",
        "total_blocks": len(blocks),
        "blocks": blocks,
        "blockchain_mode": "MOCK_FABRIC_ADAPTER"
    }

@app.get("/api/ledger/blocks/{block_num}")
def get_fabric_block(block_num: int, user=Depends(current_user)):
    db = connection()
    block = db.execute("SELECT * FROM ledger_blocks WHERE block_num=?", (block_num,)).fetchone()
    db.close()
    if not block:
        raise HTTPException(404, f"Block #{block_num} not found on channel.")

    result = dict(block)
    result["endorsers"] = json.loads(result["endorsers"])
    result["tx_payload"] = json.loads(result["tx_payload"])
    return result

@app.get("/api/blockchain/verify/{document_id}")
def verify_document_blockchain_proof(document_id: str, user=Depends(current_user)):
    db = connection()
    doc = db.execute("SELECT original_hash FROM documents WHERE id=?", (document_id,)).fetchone()
    db.close()
    if not doc:
        raise HTTPException(404, "Document not found.")

    return ledger.verify_document_proof(document_id, doc["original_hash"])

# ================= CHAIN OF CUSTODY =================

@app.get("/api/custody/{document_id}")
def get_custody_chain(document_id: str, user=Depends(current_user)):
    db = connection()
    records = [dict(x) for x in db.execute("SELECT * FROM custody WHERE document_id=? ORDER BY id DESC", (document_id,)).fetchall()]
    db.close()
    return records

@app.post("/api/custody/{document_id}")
def transfer_custody(
    document_id: str,
    to_user: str = Form(),
    purpose: str = Form(),
    signature: str = Form(),
    user=Depends(current_user)
):
    if signature != "demo-sign":
        audit(user, "CUSTODY_TRANSFER", "DENIED", document_id=document_id, reason="Invalid eSign passphrase")
        raise HTTPException(403, "Step-up digital signature verification failed.")

    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found in evidence registry.")

    proof = f"CUSTODY-SIG-{uuid.uuid4().hex[:12].upper()}"
    ledger_receipt = ledger.record("CUSTODY_TRANSFER_ENDORSED", {
        "document_id": document_id,
        "case_id": doc["case_id"],
        "from_officer": user["id"],
        "to_recipient": to_user,
        "evidence_hash": doc["original_hash"],
        "purpose": purpose,
        "signature_proof": proof
    }, [user["org_msp"], "ForensicLab.Org2MSP"])

    db.execute(
        "INSERT INTO custody(document_id, case_id, from_user, to_user, purpose, hash, signature_ref, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (document_id, doc["case_id"], user["id"], to_user, purpose, doc["original_hash"], proof, utcnow())
    )
    db.commit()
    db.close()

    audit(
        user,
        "CUSTODY_TRANSFER",
        "SUCCESS",
        case_id=doc["case_id"],
        document_id=document_id,
        reason=f"Transferred to {to_user}. Fabric Block #{ledger_receipt['block_num']}",
        signature_proof=proof
    )

    return {
        "status": "CUSTODY_TRANSFERRED",
        "document_id": document_id,
        "from": user["id"],
        "to": to_user,
        "purpose": purpose,
        "proof": proof,
        "ledger": ledger_receipt
    }

# ================= AUDIT CHRONICLE & TAMPER EVENTS =================

@app.get("/api/audits")
def get_audit_trail(limit: int = 100, user=Depends(current_user)):
    db = connection()
    rows = [dict(x) for x in db.execute("SELECT * FROM audits ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    db.close()
    return rows

@app.get("/api/tamper-events")
def get_tamper_events(user=Depends(current_user)):
    db = connection()
    rows = [dict(x) for x in db.execute("SELECT * FROM snapshots ORDER BY detected_at DESC").fetchall()]
    db.close()
    return rows

# ================= ROLE-SPECIFIC DATA & PERMISSIONS =================

@app.get("/api/dashboard/role-data")
def get_role_specific_dashboard_data(user=Depends(current_user)):
    """Returns role-specific dashboard data with permission-based filtering"""
    db = connection()
    
    role = user["role"]
    role_display = {
        "POLICE_OFFICER": "Police Investigating Officer",
        "FORENSIC_OFFICER": "Chief Forensic Examiner",
        "JUDGE": "Principal Sessions Judge",
        "HIGHER_OFFICER": "Senior Authority (DIG/SP)",
        "ADMIN": "Security Node Administrator"
    }
    
    if role == "POLICE_OFFICER":
        # Police only sees their own cases
        my_cases = [dict(x) for x in db.execute(
            "SELECT * FROM cases WHERE assigned_officer=? ORDER BY created_at DESC",
            (user["id"],)
        ).fetchall()]
        
        # Police sees only their own documents (not forensic confidential ones)
        my_docs = [dict(x) for x in db.execute(
            "SELECT id, name, document_type, current_version, status FROM documents WHERE created_by=? ORDER BY created_at DESC LIMIT 20",
            (user["id"],)
        ).fetchall()]
        
        pending_uploads = db.execute("SELECT COUNT(*) FROM documents WHERE created_by=? AND status='PENDING'", (user["id"],)).fetchone()[0]
        
        dashboard_data = {
            "role": role,
            "role_display": role_display[role],
            "actions": ["Create Case", "Upload Document", "View My Cases", "View My Documents", "Download Document", "Create New Version"],
            "my_cases": my_cases,
            "my_documents": my_docs,
            "pending_uploads": pending_uploads,
            "can_manage_cases": True,
            "can_upload": True,
            "can_create_versions": True,
            "can_view_forensic": False,
            "can_access_confidential": False,
            "sidebar_items": ["Dashboard", "My Cases", "Create Case", "Upload Document", "Document Versions", "Access History", "Offline Queue", "Notifications"]
        }
        
    elif role == "FORENSIC_OFFICER":
        # Forensic only sees assigned cases
        assigned_cases = [dict(x) for x in db.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()]
        
        # Forensic sees only forensic-labeled documents
        forensic_docs = [dict(x) for x in db.execute(
            "SELECT id, name, document_type, current_version, status FROM documents WHERE document_type LIKE '%Forensic%' OR department='Forensics' ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
        
        dashboard_data = {
            "role": role,
            "role_display": role_display[role],
            "actions": ["Upload Forensic Report", "Upload Evidence Analysis", "Verify Integrity", "View Assigned Cases"],
            "assigned_cases": assigned_cases,
            "forensic_documents": forensic_docs,
            "can_manage_cases": False,
            "can_upload": True,
            "can_create_versions": True,
            "can_view_police": False,
            "can_access_confidential": False,
            "sidebar_items": ["Dashboard", "Assigned Files", "Upload Forensic Report", "Evidence Analysis", "Versions", "Integrity Check", "Audit"]
        }
        
    elif role == "JUDGE":
        # Judge sees all authorized cases and documents
        all_cases = [dict(x) for x in db.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()]
        
        all_docs = [dict(x) for x in db.execute(
            "SELECT id, name, document_type, current_version, status FROM documents ORDER BY created_at DESC LIMIT 30"
        ).fetchall()]
        
        dashboard_data = {
            "role": role,
            "role_display": role_display[role],
            "actions": ["Review Cases", "View Evidence", "Verify Integrity", "Request Confidential Access", "Issue Rulings"],
            "all_cases": all_cases,
            "all_documents": all_docs,
            "can_manage_cases": False,
            "can_upload": False,
            "can_view_all": True,
            "can_request_confidential": True,
            "sidebar_items": ["Dashboard", "Cases", "Documents", "Evidence", "Integrity Verification", "Audit Trail", "Access Requests"]
        }
        
    elif role == "HIGHER_OFFICER":
        # Higher officer sees all cases and documents, can approve access
        all_cases = [dict(x) for x in db.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()]
        
        all_docs = [dict(x) for x in db.execute(
            "SELECT id, name, document_type, current_version, status FROM documents ORDER BY created_at DESC LIMIT 30"
        ).fetchall()]
        
        tamper_alerts = db.execute("SELECT COUNT(*) FROM documents WHERE status='TAMPERED'").fetchone()[0]
        
        dashboard_data = {
            "role": role,
            "role_display": role_display[role],
            "actions": ["Oversee Cases", "Review Access Requests", "Approve Sensitive Access", "View Tamper Alerts", "Department Activity"],
            "all_cases": all_cases,
            "all_documents": all_docs,
            "tamper_alerts": tamper_alerts,
            "can_manage_cases": True,
            "can_approve_access": True,
            "can_view_all": True,
            "sidebar_items": ["Dashboard", "Cases", "Oversight", "E-Sign & Confidential Access", "Access Requests", "Security Alerts", "Audit", "Verification"]
        }
        
    elif role == "ADMIN":
        # Admin has complete governance access
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_cases = db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        total_docs = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        total_blocks = db.execute("SELECT COUNT(*) FROM ledger_blocks").fetchone()[0]
        tamper_incidents = db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        
        dashboard_data = {
            "role": role,
            "role_display": role_display[role],
            "actions": ["Manage Users", "Manage Permissions", "View System Logs", "Monitor Blockchain", "System Settings"],
            "stats": {
                "total_users": total_users,
                "total_cases": total_cases,
                "total_documents": total_docs,
                "total_blocks": total_blocks,
                "tamper_incidents": tamper_incidents
            },
            "can_manage_users": True,
            "can_manage_permissions": True,
            "can_view_all": True,
            "can_manage_system": True,
            "sidebar_items": ["Dashboard", "Users", "Roles", "Permissions", "Cases", "Documents", "Audit", "Security", "E-Sign & Confidential Access", "Blockchain", "Cloud", "System Settings"]
        }
    else:
        dashboard_data = {"role": role, "role_display": "Unknown Role", "error": "Role not recognized"}
    
    db.close()
    return dashboard_data

@app.get("/api/document-versions/all")
@app.get("/api/documents/versions/all")
def get_all_document_versions(user=Depends(current_user)):
    """Returns complete version history across all vault documents"""
    db = connection()
    rows = [dict(x) for x in db.execute("""
        SELECT dv.id as version_record_id, dv.document_id, dv.case_id, dv.version_num,
               dv.file_hash, dv.parent_hash, dv.reason, dv.created_by, dv.created_at,
               d.name as document_name, d.document_type, d.department, d.status as doc_status,
               u.name as user_name, u.role as user_role
        FROM document_versions dv
        LEFT JOIN documents d ON dv.document_id = d.id
        LEFT JOIN users u ON dv.created_by = u.id
        ORDER BY dv.created_at DESC
    """).fetchall()]
    db.close()
    
    formatted = []
    for r in rows:
        action = "ORIGINAL" if r["version_num"] == 1 else "EDITED"
        formatted.append({
            "version_id": r["version_record_id"],
            "document_id": r["document_id"],
            "document_name": r["document_name"] or r["document_id"],
            "case_id": r["case_id"],
            "version": f"V{r['version_num']}",
            "version_num": r["version_num"],
            "action": action,
            "user": r["user_name"] or r["created_by"],
            "role": r["user_role"] or "Police Officer",
            "timestamp": r["created_at"],
            "reason": r["reason"],
            "sha256": r["file_hash"],
            "parent_hash": r["parent_hash"],
            "status": "VERIFIED" if r["doc_status"] != "TAMPERED" else "TAMPERED"
        })
    return formatted

@app.get("/api/case-categories")
def get_case_categories(user=Depends(current_user)):
    """Returns list of case categories available"""
    if user["role"] == "FORENSIC_OFFICER":
        raise HTTPException(403, "Forensic officers cannot manage case categories.")
    
    return {
        "categories": CASE_TYPES,
        "allowed_for_role": user["role"] in ("POLICE_OFFICER", "HIGHER_OFFICER", "JUDGE", "ADMIN")
    }

@app.get("/api/documents/{document_id}/edit-history")
def get_document_edit_history(document_id: str, user=Depends(current_user)):
    """Returns document edit/version history with authorization info"""
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found.")
    
    versions = [dict(x) for x in db.execute(
        "SELECT * FROM document_versions WHERE document_id=? ORDER BY version_num ASC",
        (document_id,)
    ).fetchall()]
    
    db.close()
    
    return {
        "document_id": document_id,
        "document_name": doc["name"],
        "original_hash": doc["original_hash"],
        "current_version": doc["current_version"],
        "total_versions": len(versions),
        "versions": versions,
        "status": doc["status"]
    }

@app.get("/api/permissions/check")
def check_document_access_permission(document_id: str, user=Depends(current_user)):
    """Check if current user has permission to access a document"""
    db = connection()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    db.close()
    
    if not doc:
        raise HTTPException(404, "Document not found.")
    
    # Admin and Judge always have access
    if user["role"] in ("JUDGE", "ADMIN", "HIGHER_OFFICER"):
        return {"can_access": True, "reason": "Role has holistic access"}
    
    # Police cannot see forensic confidential documents
    if user["role"] == "POLICE_OFFICER" and doc["department"] == "Forensics" and doc["is_confidential"]:
        return {"can_access": False, "reason": "Forensic confidential documents not accessible to police"}
    
    # Forensic cannot see police confidential documents
    if user["role"] == "FORENSIC_OFFICER" and doc["department"] == "Police" and doc["is_confidential"]:
        return {"can_access": False, "reason": "Police confidential documents not accessible to forensic"}
    
    # Creator always has access
    if doc["created_by"] == user["id"]:
        return {"can_access": True, "reason": "You created this document"}
    
    return {"can_access": True, "reason": "Access granted"}

# ================= STATIC FRONTEND SERVING =================

@app.get("/", response_class=HTMLResponse)
def frontend_view():
    candidates = [
        ROOT / "frontend" / "index.html",
        Path.cwd() / "frontend" / "index.html",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "index.html",
        Path(__file__).resolve().parent.parent / "frontend" / "index.html",
        Path("/var/task/frontend/index.html")
    ]
    for p in candidates:
        if p.exists():
            return HTMLResponse(content=p.read_text(encoding="utf-8", errors="ignore"), status_code=200)
    return HTMLResponse("<h1>JusticeVault UI</h1><p>Frontend file not found.</p>", status_code=200)
