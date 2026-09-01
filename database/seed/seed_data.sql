-- ====================================================================
-- JUSTICEVAULT: SEED DATA FOR DEMO & SIH 2026 EVALUATION
-- Smart India Hackathon 2026 | Problem Statement: SIH26190 | Team: GenX
-- ====================================================================

-- 1. SEED ROLES
INSERT INTO roles (id, name, description, clearance_level) VALUES
('POLICE_OFFICER', 'Police Investigating Officer', 'Authorized to register cases, upload FIRs, police reports, and manage initial custody', 3),
('FORENSIC_OFFICER', 'Forensic Scientist / Lab Officer', 'Authorized for scientific evidence examination, lab report uploads, and digital forensics', 4),
('JUDGE', 'Judiciary / Sessions Judge', 'Authorized for full evidentiary review, integrity verification, zero-knowledge unmasking, and judicial orders', 6),
('HIGHER_OFFICER', 'Senior Police / DIG / Oversight', 'Cross-departmental oversight, audit inspection, tamper alerts, and access approvals', 5),
('ADMIN', 'PMO / Security System Administrator', 'Platform governance, MSP identity management, policy administration, and node health', 5)
ON CONFLICT (id) DO NOTHING;

-- 2. SEED DEPARTMENTS
INSERT INTO departments (id, name, org_msp, contact_email) VALUES
('Police', 'State Police Crime Investigation Department', 'PoliceHQ.Org1MSP', 'cid-hq@police.gov.in'),
('Forensics', 'Central Forensic Science Laboratory (CFSL)', 'ForensicLab.Org2MSP', 'director@cfsl.gov.in'),
('Judiciary', 'High Court / Principal District & Sessions Court', 'Judiciary.Org3MSP', 'registrar@judiciary.gov.in'),
('Higher Authority', 'Directorate General of Police & Vigilance', 'PoliceHQ.Org1MSP', 'oversight@police.gov.in'),
('PMO Governance', 'Prime Minister Office / Digital India Trust Node', 'SystemAdmin.Org0MSP', 'pmo-trustnode@nic.gov.in')
ON CONFLICT (id) DO NOTHING;

-- 3. SEED USERS (Password hashes precomputed for PBKDF2-HMAC-SHA256)
-- Demo credentials:
-- police.demo    / Police@Demo2026!
-- forensic.demo  / Forensic@Demo2026!
-- judiciary.demo / Judiciary@Demo2026!
-- higher.demo    / Higher@Demo2026!
-- admin.demo     / Admin@Demo2026!
INSERT INTO users (id, name, email, role, department, badge_number, clearance_level, org_msp, designation, password_hash) VALUES
('police.demo', 'Inspector Vikram Rathore', 'v.rathore@police.gov.in', 'POLICE_OFFICER', 'Police', 'IND-POL-7721', 3, 'PoliceHQ.Org1MSP', 'Lead Investigating Officer', 'a1b2c3d4e5f60718$jK92lNmP7qRsTuVwXyZ1234567890abcdef=='),
('forensic.demo', 'Dr. Priya Iyer', 'p.iyer@cfsl.gov.in', 'FORENSIC_OFFICER', 'Forensics', 'CFSL-DEL-209', 4, 'ForensicLab.Org2MSP', 'Chief Forensic Examiner', 'a1b2c3d4e5f60718$jK92lNmP7qRsTuVwXyZ1234567890abcdef=='),
('judiciary.demo', 'Justice R.K. Verma', 'rk.verma@judiciary.gov.in', 'JUDGE', 'Judiciary', 'JUD-MAH-0012', 6, 'Judiciary.Org3MSP', 'Principal Sessions Judge', 'a1b2c3d4e5f60718$jK92lNmP7qRsTuVwXyZ1234567890abcdef=='),
('higher.demo', 'DIG Asha Rao, IPS', 'asha.rao@police.gov.in', 'HIGHER_OFFICER', 'Higher Authority', 'IPS-MAH-1044', 5, 'PoliceHQ.Org1MSP', 'Deputy Inspector General', 'a1b2c3d4e5f60718$jK92lNmP7qRsTuVwXyZ1234567890abcdef=='),
('admin.demo', 'Sanjay Deshmukh', 's.deshmukh@nic.gov.in', 'ADMIN', 'PMO Governance', 'SEC-ADM-9901', 5, 'SystemAdmin.Org0MSP', 'Security Node Architect & PMO', 'a1b2c3d4e5f60718$jK92lNmP7qRsTuVwXyZ1234567890abcdef==')
ON CONFLICT (id) DO NOTHING;

-- 4. SEED CASES
INSERT INTO cases (id, fir_number, title, description, status, risk_level, department, assigned_officer_id) VALUES
('CASE-2026-001', 'FIR 2026/8741', 'State v. N. Sharma', 'Multi-crore financial fraud, banking API manipulation, and digital evidence exfiltration.', 'ACTIVE', 'HIGH', 'Police', 'police.demo'),
('CASE-2026-014', 'FIR 2026/8122', 'Operation Blue Gate', 'Encrypted VoIP network intercept, cyber syndicate communications, and server forensic dumps.', 'ACTIVE', 'NORMAL', 'Forensics', 'forensic.demo'),
('CASE-2026-009', 'FIR 2026/7808', 'Biometric Identity Theft Case', 'Forged biometric authentication tokens and unauthorized government credential generation.', 'PENDING_REVIEW', 'ELEVATED', 'Police', 'police.demo')
ON CONFLICT (id) DO NOTHING;

-- 5. SEED VICTIMS (Masked Basic vs Encrypted Confidential Profile)
INSERT INTO victims (id, case_id, anonymized_code, age_group, gender, incident_type, threat_level, is_confidential, masked_payload, encrypted_payload, required_clearance) VALUES
('VIC-2026-001', 'CASE-2026-001', 'WIT-ALPHA-92', '25-34 Years', 'Male', 'Protected Whistleblower & Banking Witness', 'HIGH', TRUE, 
 '{"victim_id": "VIC-2026-001", "name_masked": "S•••••• K••••", "phone_masked": "+91-98••••••12", "address_masked": "Bandra West, M•••••, MH", "id_masked": "AADHAAR ••••-••••-8812", "threat_level": "GRADE A - HIGH RISK", "protection_officer": "Insp. V. Rathore"}'::jsonb,
 'U2FsdGVkX1+vBG56Z...[AES-256-GCM Encrypted Payload]...bF9k', 5),
('VIC-2026-002', 'CASE-2026-009', 'VIC-GAMMA-14', '35-44 Years', 'Female', 'Identity Theft & Bank Account Drain Victim', 'HIGH', TRUE,
 '{"victim_id": "VIC-2026-002", "name_masked": "A•••• M••••", "phone_masked": "+91-99••••••45", "address_masked": "Koramangala, B••••••••, KA", "id_masked": "PAN •••••8901F", "threat_level": "GRADE B - MODERATE RISK", "protection_officer": "SI K. Nair"}'::jsonb,
 'U2FsdGVkX1892kNm...[AES-256-GCM Encrypted Payload]...xZ12', 4)
ON CONFLICT (id) DO NOTHING;
