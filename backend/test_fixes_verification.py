import os
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_complete_fixes_verification():
    print("\n" + "="*60)
    print(" JUSTICEVAULT FIXES VERIFICATION SUITE ")
    print("="*60)

    # 1. Test Login as Police Officer
    print("\n1. Testing Login as Police Officer (police.demo)...")
    res = client.post("/api/auth/login", data={"username": "police.demo", "password": "Police@Demo2026!"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    login_data = res.json()
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  ✓ Authenticated as:", login_data["user"]["name"], f"({login_data['user']['role']})")

    # 2. Test Create Case with Clean JSON Payload
    print("\n2. Testing Create Case with Clean JSON Payload...")
    case_payload = {
        "caseTitle": "State v. Advanced Cyber Ransomware Ring",
        "caseType": "CYBER_CRIME",
        "policeStation": "Cyber Crime Branch HQ",
        "investigatingOfficer": "Inspector Vikram Rathore",
        "priority": "HIGH",
        "description": "Cross-border ransomware deployment targeting critical healthcare and banking APIs.",
        "incidentDate": "2026-09-01",
        "location": "Mumbai Cyber Jurisdiction",
        "referenceNumber": "REF-CC-2026-99"
    }
    case_res = client.post("/api/cases", json=case_payload, headers=headers)
    assert case_res.status_code == 200, f"Case creation failed: {case_res.text}"
    case_json = case_res.json()
    assert case_json["success"] is True
    assert case_json["data"]["case_id"].startswith("JV-")
    assert case_json["data"]["case_type"] == "CYBER_CRIME"
    assert case_json["data"]["blockchain_message"] == "BLOCKCHAIN: MOCK MODE"
    print(f"  ✓ Case Created Successfully: {case_json['data']['case_id']}")
    print(f"  ✓ Case Type: {case_json['data']['case_type']}")
    print(f"  ✓ Status: {case_json['data']['status']}")
    print(f"  ✓ Blockchain Mode: {case_json['data']['blockchain_message']}")

    # 3. Test Field Validation Failure & Structured Error Extraction (No [object Object])
    print("\n3. Testing Field Validation Error Handling...")
    invalid_payload = {
        "caseTitle": "", # missing title
        "caseType": "",  # missing type
        "policeStation": "Cyber Crime HQ",
        "investigatingOfficer": "Inspector Vikram Rathore",
        "priority": "NORMAL",
        "description": "abc" # too short
    }
    val_res = client.post("/api/cases", json=invalid_payload, headers=headers)
    assert val_res.status_code == 422
    val_json = val_res.json()
    assert val_json["success"] is False
    assert val_json["error"]["code"] == "VALIDATION_ERROR"
    assert "caseTitle" in val_json["error"]["fields"]
    assert "caseType" in val_json["error"]["fields"]
    assert "description" in val_json["error"]["fields"]
    print("  ✓ Structured Validation Error returned cleanly:")
    print("    ", json.dumps(val_json["error"], indent=2))

    # 4. Test Role-Specific Case Category Access (Forensic Denied, Police Allowed)
    print("\n4. Testing Role-Specific Category Permissions...")
    # Police allows categories
    cat_res = client.get("/api/case-categories", headers=headers)
    assert cat_res.status_code == 200
    assert len(cat_res.json()["categories"]) >= 13
    print(f"  ✓ Police Officer can access {len(cat_res.json()['categories'])} case categories")

    # Forensic login
    forensic_login = client.post("/api/auth/login", data={"username": "forensic.demo", "password": "Forensic@Demo2026!"}).json()
    forensic_headers = {"Authorization": f"Bearer {forensic_login['access_token']}"}
    
    # Forensic denied categories
    forensic_cat_res = client.get("/api/case-categories", headers=forensic_headers)
    assert forensic_cat_res.status_code == 403
    print("  ✓ Forensic Officer forbidden from managing case categories (403)")

    # Forensic denied case creation
    forensic_case_res = client.post("/api/cases", json=case_payload, headers=forensic_headers)
    assert forensic_case_res.status_code == 403
    print("  ✓ Forensic Officer forbidden from creating cases (403)")

    # 5. Test Document Versions Timeline
    print("\n5. Testing Document Versions Endpoint (/api/document-versions/all)...")
    ver_res = client.get("/api/document-versions/all", headers=headers)
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) > 0
    first_ver = versions[0]
    assert first_ver["action"] in ("ORIGINAL", "EDITED")
    print(f"  ✓ Retrieved {len(versions)} immutable version entries across vault documents")
    print(f"    Sample: Doc: {first_ver['document_name']}, Version: {first_ver['version']}, Action: {first_ver['action']}, Status: {first_ver['status']}")

    # 6. Test Access History Audit Chronicle
    print("\n6. Testing Access History Audit Chronicle (/api/audits)...")
    audit_res = client.get("/api/audits?limit=10", headers=headers)
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) > 0
    print(f"  ✓ Retrieved {len(audits)} audit records with WHO, WHAT, WHEN, WHY, RESULT")
    print(f"    Latest: {audits[0]['action']} ({audits[0]['result']}) by {audits[0]['user_id']}")

    # 7. Test Root Frontend Serving
    print("\n7. Testing Frontend Serving (GET /)...")
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "JUSTICEVAULT" in root_res.text
    assert "getErrorMessage" in root_res.text
    print(f"  ✓ Frontend index.html served successfully ({len(root_res.text)} bytes)")

    print("\n" + "="*60)
    print(" ALL FIXES VERIFICATION TESTS PASSED SUCCESSFULLY! ")
    print("="*60)

if __name__ == "__main__":
    test_complete_fixes_verification()
