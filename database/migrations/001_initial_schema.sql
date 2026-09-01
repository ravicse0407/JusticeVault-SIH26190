-- ====================================================================
-- JUSTICEVAULT: SECURE DIGITAL EVIDENCE & LEGAL DOCUMENT TRUST PLATFORM
-- Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
-- PostgreSQL Production Schema Migration 001_initial_schema.sql
-- ====================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. ROLES & PERMISSIONS
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    clearance_level INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(100) PRIMARY KEY,
    role_id VARCHAR(50) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    conditions JSONB DEFAULT '{}'::jsonb
);

-- 2. DEPARTMENTS
CREATE TABLE IF NOT EXISTS departments (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    org_msp VARCHAR(100) NOT NULL,
    contact_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. USERS
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(50) NOT NULL REFERENCES roles(id),
    department VARCHAR(50) NOT NULL,
    badge_number VARCHAR(100) NOT NULL,
    clearance_level INT NOT NULL DEFAULT 1,
    org_msp VARCHAR(100) NOT NULL,
    designation VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    public_key TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. CASES
CREATE TABLE IF NOT EXISTS cases (
    id VARCHAR(100) PRIMARY KEY,
    fir_number VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, UNDER_INVESTIGATION, IN_TRIAL, CLOSED
    risk_level VARCHAR(50) NOT NULL DEFAULT 'NORMAL', -- LOW, NORMAL, ELEVATED, HIGH, CRITICAL
    department VARCHAR(50) NOT NULL,
    assigned_officer_id VARCHAR(100) NOT NULL REFERENCES users(id),
    court_jurisdiction VARCHAR(200),
    is_sealed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. DOCUMENTS
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(100) PRIMARY KEY,
    case_id VARCHAR(100) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(100) NOT NULL, -- FIR, POLICE_REPORT, FORENSIC_REPORT, CHARGESHEET, LAB_FINDINGS, SEIZURE_MEMO, VICTIM_STATEMENT
    department VARCHAR(50) NOT NULL,
    current_version INT NOT NULL DEFAULT 1,
    original_hash VARCHAR(64) NOT NULL, -- SHA-256 baseline
    current_hash VARCHAR(64) NOT NULL,  -- SHA-256 current
    status VARCHAR(50) NOT NULL DEFAULT 'INTACT', -- INTACT, TAMPERED, ARCHIVED, SEALED
    is_confidential BOOLEAN NOT NULL DEFAULT FALSE,
    classification VARCHAR(50) NOT NULL DEFAULT 'RESTRICTED', -- UNCLASSIFIED, CONFIDENTIAL, SECRET, TOP_SECRET
    vault_path VARCHAR(500) NOT NULL,
    encryption_algorithm VARCHAR(50) NOT NULL DEFAULT 'AES-256-GCM',
    blockchain_tx_id VARCHAR(128),
    created_by VARCHAR(100) NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. DOCUMENT VERSIONS (IMMUTABLE RECORD PRESERVATION)
CREATE TABLE IF NOT EXISTS document_versions (
    id VARCHAR(100) PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    case_id VARCHAR(100) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    version_num INT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    parent_hash VARCHAR(64),
    reason TEXT NOT NULL,
    vault_path VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    blockchain_tx_id VARCHAR(128),
    created_by VARCHAR(100) NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_doc_version UNIQUE (document_id, version_num)
);

-- 7. DOCUMENT ACCESS POLICIES & ACL
CREATE TABLE IF NOT EXISTS document_access (
    id VARCHAR(100) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(100) REFERENCES users(id) ON DELETE CASCADE,
    role_id VARCHAR(50) REFERENCES roles(id) ON DELETE CASCADE,
    permission_level VARCHAR(50) NOT NULL DEFAULT 'READ', -- READ, EDIT, SIGN, ADMIN
    granted_by VARCHAR(100) NOT NULL REFERENCES users(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 8. DOCUMENT SHARES (EXPLICIT CROSS-DEPARTMENT SHARING)
CREATE TABLE IF NOT EXISTS document_shares (
    id VARCHAR(100) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    from_dept VARCHAR(50) NOT NULL,
    to_dept VARCHAR(50) NOT NULL,
    shared_by VARCHAR(100) NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    shared_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 9. VICTIM PRIVACY (BASIC MINIMUM PROFILE)
CREATE TABLE IF NOT EXISTS victims (
    id VARCHAR(100) PRIMARY KEY,
    case_id VARCHAR(100) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    anonymized_code VARCHAR(100) NOT NULL, -- e.g. VIC-ALPHA-92
    age_group VARCHAR(50) NOT NULL,       -- e.g. 25-34 Years
    gender VARCHAR(50),
    incident_type VARCHAR(200) NOT NULL,
    threat_level VARCHAR(50) NOT NULL DEFAULT 'HIGH', -- LOW, MEDIUM, HIGH, PROTECTED_WITNESS
    is_confidential BOOLEAN NOT NULL DEFAULT TRUE,
    masked_payload JSONB NOT NULL,
    encrypted_payload TEXT NOT NULL,      -- Encrypted with server-side AES-256-GCM
    required_clearance INT NOT NULL DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. VICTIM SENSITIVE DATA LOGS & UNLOCKS
CREATE TABLE IF NOT EXISTS victim_sensitive_data_access (
    id VARCHAR(100) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    victim_id VARCHAR(100) NOT NULL REFERENCES victims(id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    purpose VARCHAR(255) NOT NULL,
    esign_proof VARCHAR(255) NOT NULL,
    fields_accessed JSONB NOT NULL,
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. STEP-UP E-SIGN AUTHORIZATION RECORDS
CREATE TABLE IF NOT EXISTS esign_records (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id),
    resource_type VARCHAR(100) NOT NULL, -- VICTIM_PII, CONFIDENTIAL_REPORT, SEALED_EVIDENCE
    resource_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    purpose TEXT NOT NULL,
    legal_basis VARCHAR(255) NOT NULL,
    signature_proof VARCHAR(255) NOT NULL, -- SHA-256 HMAC of authorization payload
    public_cert_fingerprint VARCHAR(64),
    blockchain_tx_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. FORENSIC TAMPER INCIDENTS & QUARANTINE SNAPSHOTS
CREATE TABLE IF NOT EXISTS tamper_events (
    id VARCHAR(100) PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    case_id VARCHAR(100) REFERENCES cases(id) ON DELETE SET NULL,
    original_hash VARCHAR(64) NOT NULL,
    detected_hash VARCHAR(64) NOT NULL,
    quarantine_vault_path VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'UNTRUSTED_QUARANTINED',
    detected_by VARCHAR(100) NOT NULL REFERENCES users(id),
    blockchain_incident_block INT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. IMMUTABLE AUDIT LOG (APPEND-ONLY)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL DEFAULT uuid_generate_v4()::text,
    user_id VARCHAR(100),
    role VARCHAR(50),
    department VARCHAR(50),
    case_id VARCHAR(100),
    document_id VARCHAR(100),
    action VARCHAR(100) NOT NULL, -- LOGIN, LOGOUT, DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD, DOCUMENT_EDIT, DOCUMENT_VERSION_CREATED, TAMPER_DETECTED, etc.
    result VARCHAR(50) NOT NULL,  -- SUCCESS, DENIED, TAMPER_TRIGGERED, ERROR
    reason TEXT,
    previous_version VARCHAR(64),
    new_version VARCHAR(64),
    signature_proof VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    blockchain_tx_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. OFFLINE SYNC QUEUE
CREATE TABLE IF NOT EXISTS sync_queue (
    id VARCHAR(100) PRIMARY KEY,
    case_id VARCHAR(100) NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    encrypted_blob_size BIGINT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'WAITING', -- WAITING, SYNCED, FAILED
    user_id VARCHAR(100) NOT NULL REFERENCES users(id),
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_at TIMESTAMPTZ
);

-- 15. HYPERLEDGER FABRIC TRANSACTIONS & PROOFS
CREATE TABLE IF NOT EXISTS blockchain_transactions (
    tx_id VARCHAR(128) PRIMARY KEY,
    block_num INT NOT NULL,
    channel_id VARCHAR(100) NOT NULL DEFAULT 'channel-legal-evidence',
    chaincode_id VARCHAR(100) NOT NULL DEFAULT 'evidence_cc',
    function_name VARCHAR(100) NOT NULL,
    document_id VARCHAR(100),
    case_id VARCHAR(100),
    doc_hash VARCHAR(64),
    signer_msp VARCHAR(100) NOT NULL,
    signer_id VARCHAR(100) NOT NULL,
    payload_json JSONB NOT NULL,
    prev_block_hash VARCHAR(64) NOT NULL,
    block_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. ACCESS REQUESTS & APPROVAL WORKFLOW
CREATE TABLE IF NOT EXISTS access_requests (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id),
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    approved_by VARCHAR(100) REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- 17. NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(100) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id VARCHAR(100) NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'INFO', -- INFO, WARNING, TAMPER_ALERT, ACCESS_REQUEST
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- INDEXES FOR HIGH-PERFORMANCE PROVENANCE SEARCH
CREATE INDEX IF NOT EXISTS idx_docs_case ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(current_hash);
CREATE INDEX IF NOT EXISTS idx_versions_doc ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_doc ON audit_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_blockchain_doc ON blockchain_transactions(document_id);
CREATE INDEX IF NOT EXISTS idx_tamper_doc ON tamper_events(document_id);
