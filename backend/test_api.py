import os
import sys
from fastapi.testclient import TestClient

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.core import init_db

# Re-init db for testing
init_db()

client = TestClient(app)

def test_justicevault_full_suite():
    print("==================================================")
    print(" JUSTICEVAULT SIH26190 AUTOMATED VERIFICATION ")
    print("==================================================")

    # 1. Health & Platform Status
    print("\n1. Testing /api/health...")
    r = client.get("/api/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health = r.json()
    assert health["platform"] == "JUSTICEVAULT"
    assert health["team"] == "GenX"
    print("✓ Platform Status:", health)

    # 2. Test All 5 Role Logins
    print("\n2. Testing 5 SIH Role Logins...")
    roles = [
        ("police.demo", "Police@Demo2026!", "POLICE_OFFICER", 3),
        ("forensic.demo", "Forensic@Demo2026!", "FORENSIC_OFFICER", 4),
        ("judiciary.demo", "Judiciary@Demo2026!", "JUDGE", 6),
        ("higher.demo", "Higher@Demo2026!", "HIGHER_OFFICER", 5),
        ("admin.demo", "Admin@Demo2026!", "ADMIN", 5)
    ]

    tokens = {}
    for user, pwd, expected_role, expected_clr in roles:
        r = client.post("/api/auth/login", data={"username": user, "password": pwd})
        assert r.status_code == 200, f"Login failed for {user}: {r.text}"
        data = r.json()
        assert data["user"]["role"] == expected_role
        assert data["user"]["clearance"] == expected_clr
        tokens[user] = data["access_token"]
        print(f"  ✓ {user} -> {data['user']['name']} ({data['user']['role']}, L{data['user']['clearance']})")

    police_headers = {"Authorization": f"Bearer {tokens['police.demo']}"}
    forensic_headers = {"Authorization": f"Bearer {tokens['forensic.demo']}"}
    judge_headers = {"Authorization": f"Bearer {tokens['judiciary.demo']}"}
    higher_headers = {"Authorization": f"Bearer {tokens['higher.demo']}"}
    admin_headers = {"Authorization": f"Bearer {tokens['admin.demo']}"}

    # 3. Case Creation & Listing
    print("\n3. Testing Case Creation (Police Officer)...")
    r = client.post(
        "/api/cases",
        data={
            "case_id": "CASE-2026-099",
            "fir_number": "FIR 2026/9999",
            "title": "State v. Cyber Infiltration Node",
            "description": "Critical infrastructure cyber intrusion and evidence analysis.",
            "risk_level": "HIGH"
        },
        headers=police_headers
    )
    assert r.status_code == 200, f"Case creation failed: {r.text}"
    case_res = r.json()
    print(f"✓ Case created: {case_res['case_id']}, Fabric Block #{case_res['ledger']['block_num']}")

    # 4. Document Upload & Vault Encryption
    print("\n4. Testing Document Upload & Vault Encryption (Police Officer)...")
    fir_content = b"%PDF-1.4 Official FIR Copy 2026 - Investigation Unit Alpha"
    r = client.post(
        "/api/documents",
        data={"case_id": "CASE-2026-099", "document_type": "First Information Report (FIR)", "is_confidential": 0},
        files={"file": ("FIR_2026_9999.pdf", fir_content, "application/pdf")},
        headers=police_headers
    )
    assert r.status_code == 200, f"Document upload failed: {r.text}"
    doc_res = r.json()
    doc_id = doc_res["document_id"]
    print(f"✓ Document {doc_id} encrypted & deposited in vault. Hash: {doc_res['sha256'][:16]}... Block #{doc_res['ledger']['block_num']}")

    # 5. Document Integrity Verification
    print(f"\n5. Testing Document Integrity Verification ({doc_id})...")
    r = client.get(f"/api/documents/{doc_id}/verify", headers=police_headers)
    assert r.status_code == 200
    assert r.json()["integrity"] == "INTACT"
    print("✓ Integrity Verified: INTACT")

    # 6. Version Control (Original Preservation)
    print(f"\n6. Testing Version Control on {doc_id}...")
    v2_content = fir_content + b"\n[SUPPLEMENTARY WITNESS TESTIMONY RECORDED 01-SEP-2026]"
    r = client.post(
        f"/api/documents/{doc_id}/versions",
        data={"reason": "Added supplementary witness statement"},
        files={"file": ("FIR_2026_9999_v2.pdf", v2_content, "application/pdf")},
        headers=police_headers
    )
    assert r.status_code == 200, f"Version creation failed: {r.text}"
    v2_res = r.json()
    assert v2_res["version"] == 2
    print(f"✓ Created Version V2. Parent Hash: {v2_res['parent_hash'][:16]}... New Hash: {v2_res['new_hash'][:16]}... Block #{v2_res['ledger']['block_num']}")

    # Check version history
    r = client.get(f"/api/documents/{doc_id}/versions", headers=police_headers)
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) == 2
    print(f"✓ Retrieved version timeline: {len(versions)} immutable versions recorded.")

    # 7. Document Download
    print(f"\n7. Testing Decrypted Document Download...")
    r = client.get(f"/api/documents/{doc_id}/download", headers=police_headers)
    assert r.status_code == 200
    assert len(r.content) > 0
    print(f"✓ Downloaded decrypted payload ({len(r.content)} bytes). Content-Disposition: {r.headers.get('content-disposition')}")

    # 8. Tamper Detection & Quarantined Forensic Preservation
    print(f"\n8. Testing Forensic Tamper Detection Demo on {doc_id}...")
    tampered_bytes = b"MALICIOUS ALTERATION OF EVIDENCE BY ADVERSARY"
    r = client.post(
        f"/api/documents/{doc_id}/verify-upload",
        files={"file": ("FIR_2026_9999.pdf", tampered_bytes, "application/pdf")},
        headers=police_headers
    )
    assert r.status_code == 200
    tamper_res = r.json()
    assert tamper_res["integrity"] == "TAMPERED"
    assert "UNTRUSTED" in tamper_res["status"]
    snap_id = tamper_res["snapshot_id"]
    print(f"✓ Tamper Detected! Quarantine Snapshot: {snap_id}, Fabric Incident Block #{tamper_res['ledger']['block_num']}")

    # 9. Victim Privacy & Zero-Knowledge E-Sign Authorization
    print("\n9. Testing Victim Privacy & Zero-Knowledge eSign...")
    r = client.get("/api/victims", headers=judge_headers)
    assert r.status_code == 200
    victims = r.json()
    assert len(victims) > 0
    v_id = victims[0]["id"]

    # Basic profile is masked
    r = client.get(f"/api/victims/{v_id}/confidential", headers=police_headers)
    assert r.status_code == 200
    masked_res = r.json()
    assert "████" in masked_res["masked_data"]["full_name"] or "••••" in masked_res["masked_data"]["full_name"]
    print("✓ Confidential PII is masked by default:", masked_res["masked_data"]["full_name"])

    # E-Sign Authorization (Judge L6)
    r = client.post(
        f"/api/victims/{v_id}/esign-authorize",
        data={"certificate_type": "JUDICIAL_SEAL_DSC", "passphrase": "demo-sign", "reason": "Official Trial Review"},
        headers=judge_headers
    )
    assert r.status_code == 200, f"eSign failed: {r.text}"
    esign_res = r.json()
    assert esign_res["status"] == "DECRYPTED_ACCESS_GRANTED"
    assert "Siddharth" in esign_res["decrypted_data"]["full_name"]
    print(f"✓ eSign Authorized! Decrypted PII: {esign_res['decrypted_data']['full_name']}, Proof: {esign_res['esign_certificate']['signature_proof'][:24]}...")

    # 10. Offline-First Sync Hub
    print("\n10. Testing Offline-First Queue Sync (/api/sync)...")
    offline_queue = [
        {
            "queue_id": "OFFLINE-QUEUE-001",
            "case_id": "CASE-2026-099",
            "document_type": "Field Scene Investigation Report",
            "filename": "field_scene_log.pdf",
            "content_base64": "JVBERi0xLjQgRmllbGQgU2NlbmUgUmVwb3J0IC0gT2ZmbGluZSBDYXB0dXJlIDIwMjY="
        }
    ]
    r = client.post("/api/sync", json=offline_queue, headers=police_headers)
    assert r.status_code == 200, f"Sync failed: {r.text}"
    sync_res = r.json()
    assert sync_res["synced_count"] == 1
    print(f"✓ Synced {sync_res['synced_count']} offline document(s) to cloud vault & Fabric ledger.")

    # 11. Chain of Custody Transfer
    print("\n11. Testing Chain of Custody Transfer...")
    r = client.post(
        f"/api/custody/{doc_id}",
        data={"to_user": "forensic.demo", "purpose": "Chemical forensic examination", "signature": "demo-sign"},
        headers=police_headers
    )
    assert r.status_code == 200, f"Custody transfer failed: {r.text}"
    custody_res = r.json()
    print(f"✓ Custody transferred to forensic.demo. Proof: {custody_res['proof']}, Block #{custody_res['ledger']['block_num']}")

    # 12. Hyperledger Fabric Blockchain Explorer
    print("\n12. Testing Hyperledger Fabric Explorer (/api/ledger/blocks)...")
    r = client.get("/api/ledger/blocks", headers=judge_headers)
    assert r.status_code == 200
    blocks_data = r.json()
    print(f"✓ Total Committed Blocks on '{blocks_data['channel']}': {blocks_data['total_blocks']}. Latest block #{blocks_data['blocks'][0]['block_num']}")

    # 13. Audit Chronicle
    print("\n13. Testing Append-Only Audit Chronicle (/api/audits)...")
    r = client.get("/api/audits", headers=admin_headers)
    assert r.status_code == 200
    audits = r.json()
    print(f"✓ Total Audit Records: {len(audits)}. Latest Event: {audits[0]['action']} ({audits[0]['result']}) by {audits[0]['user_id']}")

    # 14. Frontend Root Serving
    print("\n14. Testing Frontend Root Serving (GET /)...")
    r = client.get("/")
    assert r.status_code == 200
    assert "JUSTICEVAULT" in r.text or "SLIDMS" in r.text
    print(f"✓ Frontend served successfully ({len(r.text)} bytes)")

    print("\n==================================================")
    print(" ALL 14 JUSTICEVAULT SUITE TESTS PASSED (100%)!   ")
    print("==================================================")

if __name__ == "__main__":
    test_justicevault_full_suite()
