import os
import json
from fastapi.testclient import TestClient
from app.core import init_db
from app.main import app

init_db()
client = TestClient(app)

def test_complete_esign_enforcement():
    print("\n" + "="*60)
    print(" MANDATORY PROTOTYPE E-SIGN ENFORCEMENT VERIFICATION ")
    print("="*60)

    # 1. Login as Principal Sessions Judge (judiciary.demo)
    print("\n1. Authenticating as Principal Sessions Judge (judiciary.demo)...")
    res = client.post("/api/auth/login", data={"username": "judiciary.demo", "password": "Judiciary@Demo2026!"})
    assert res.status_code == 200, f"Judge login failed: {res.text}"
    judge_token = res.json()["access_token"]
    judge_headers = {"Authorization": f"Bearer {judge_token}"}
    print("  ✓ Judge authenticated (Clearance L6)")

    # 2. Verify Judge can see restricted National Security documents
    print("\n2. Checking restricted documents visibility for Judge...")
    doc_res = client.get("/api/documents", headers=judge_headers)
    assert doc_res.status_code == 200
    docs = doc_res.json()
    natsec_docs = [d for d in docs if d.get("classification") in ("NATIONAL_SECURITY", "TOP_SECRET", "HIGHLY_CONFIDENTIAL")]
    assert len(natsec_docs) >= 1, "Expected at least 1 restricted National Security document"
    target_doc = natsec_docs[0]
    print(f"  ✓ Found restricted document: {target_doc['id']} ({target_doc['name']}) - Classification: {target_doc['classification']}")

    # 3. Attempt direct download WITHOUT E-Sign Token -> MUST BE BLOCKED (403)
    print("\n3. Testing direct download WITHOUT E-Sign token (Must be blocked)...")
    dl_blocked_res = client.get(f"/api/documents/{target_doc['id']}/download", headers=judge_headers)
    assert dl_blocked_res.status_code == 403, f"Expected 403 blocked, got {dl_blocked_res.status_code}"
    assert "E-SIGN REQUIRED" in dl_blocked_res.json()["detail"]
    print("  ✓ Backend successfully blocked unauthenticated document download (403 Forbidden)")
    print("    Message:", dl_blocked_res.json()["detail"])

    # 4. Attempt direct preview WITHOUT E-Sign Token -> MUST BE BLOCKED (403)
    print("\n4. Testing direct preview WITHOUT E-Sign token (Must be blocked)...")
    prev_blocked_res = client.get(f"/api/documents/{target_doc['id']}/preview", headers=judge_headers)
    assert prev_blocked_res.status_code == 403
    assert "E-SIGN REQUIRED" in prev_blocked_res.json()["detail"]
    print("  ✓ Backend successfully blocked unauthenticated preview (403 Forbidden)")

    # 5. Test Police and Forensic Officers CANNOT authorize or see restricted docs
    print("\n5. Testing Police & Forensic role restrictions on restricted docs...")
    police_login = client.post("/api/auth/login", data={"username": "police.demo", "password": "Police@Demo2026!"}).json()
    police_headers = {"Authorization": f"Bearer {police_login['access_token']}"}
    
    # Police docs list should not expose restricted files
    police_docs = client.get("/api/documents", headers=police_headers).json()
    police_restricted = [d for d in police_docs if d.get("classification") in ("NATIONAL_SECURITY", "TOP_SECRET")]
    assert len(police_restricted) == 0, "Police should not see restricted national security documents"
    print("  ✓ Restricted documents hidden from Police Officer document list")

    # Police E-Sign authorize attempt -> 403 Denied
    police_auth_res = client.post(
        f"/api/documents/{target_doc['id']}/esign-authorize",
        json={"purpose": "Police investigation test", "pin": "demo-sign", "passphrase": "demo-sign"},
        headers=police_headers
    )
    assert police_auth_res.status_code == 403
    print("  ✓ Police Officer forbidden from performing E-Sign on restricted document (403)")

    # 6. Test E-Sign with INVALID PIN -> Status REJECTED & 403
    print("\n6. Testing Prototype E-Sign with INVALID PIN...")
    invalid_pin_res = client.post(
        f"/api/documents/{target_doc['id']}/esign-authorize",
        json={"purpose": "Judicial in-camera review", "pin": "wrong-pin-999", "passphrase": "wrong-pin-999"},
        headers=judge_headers
    )
    assert invalid_pin_res.status_code == 403
    assert "REJECTED" in invalid_pin_res.json()["detail"]
    print("  ✓ Invalid PIN correctly rejected (403 Forbidden)")

    # 7. Test E-Sign with VALID PIN -> Status VERIFIED, Auth ID & Token Generated
    print("\n7. Testing Prototype E-Sign ceremony with VALID PIN (demo-sign)...")
    valid_auth_res = client.post(
        f"/api/documents/{target_doc['id']}/esign-authorize",
        json={"purpose": "Official Judicial In-Camera Witness & Evidence Cross-Examination", "pin": "demo-sign", "passphrase": "demo-sign"},
        headers=judge_headers
    )
    assert valid_auth_res.status_code == 200, f"E-Sign authorization failed: {valid_auth_res.text}"
    auth_data = valid_auth_res.json()
    assert auth_data["success"] is True
    assert auth_data["status"] == "VERIFIED"
    assert "PROTOTYPE E-SIGN" in auth_data["prototype_notice"]
    esign_token = auth_data["auth_token"]
    auth_id = auth_data["authorization_id"]
    print(f"  ✓ Prototype E-Sign Verified: {auth_id}")
    print(f"  ✓ Signature Proof: {auth_data['signature_proof']}")
    print(f"  ✓ Session Expires At: {auth_data['expires_at']}")
    print(f"  ✓ Prototype Disclaimer: {auth_data['prototype_notice']}")

    # 8. Test Download & Preview WITH Valid E-Sign Token -> SUCCCEEDS
    print("\n8. Testing download & preview WITH valid E-Sign token...")
    # Via query parameter
    dl_success_res = client.get(
        f"/api/documents/{target_doc['id']}/download?esign_token={esign_token}",
        headers=judge_headers
    )
    assert dl_success_res.status_code == 200
    assert len(dl_success_res.content) > 0
    print(f"  ✓ Document successfully decrypted & downloaded ({len(dl_success_res.content)} bytes)")

    # Via header preview
    prev_success_res = client.get(
        f"/api/documents/{target_doc['id']}/preview",
        headers={**judge_headers, "X-Esign-Auth-Token": esign_token}
    )
    assert prev_success_res.status_code == 200
    prev_data = prev_success_res.json()
    assert prev_data["is_restricted"] is True
    assert len(prev_data["content_text"]) > 0
    print("  ✓ Document preview unlocked:", prev_data["content_text"][:80] + "...")

    # 9. Verify E-Sign Authorizations Chronicle
    print("\n9. Testing E-Sign Authorizations Chronicle (/api/esign-authorizations)...")
    chronicle_res = client.get("/api/esign-authorizations", headers=judge_headers)
    assert chronicle_res.status_code == 200
    authorizations = chronicle_res.json()
    statuses = {a["status"] for a in authorizations}
    print(f"  ✓ Retrieved {len(authorizations)} E-Sign authorization records. Statuses recorded: {statuses}")

    print("\n" + "="*60)
    print(" ALL MANDATORY E-SIGN ENFORCEMENT TESTS PASSED (100%)! ")
    print("="*60)

if __name__ == "__main__":
    test_complete_esign_enforcement()
