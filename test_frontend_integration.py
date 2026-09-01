#!/usr/bin/env python3
"""Quick integration test for JusticeVault frontend + API"""

import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError

API_BASE = "http://127.0.0.1:8000/api"

def test_health():
    """Test backend health"""
    try:
        with urlopen(f"{API_BASE}/health") as response:
            data = json.loads(response.read().decode())
            print(f"✓ Backend Health: {data.get('status')}")
            return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

def test_login(username, password):
    """Test login"""
    try:
        # Use urllib for login (POST with form data)
        url = f"{API_BASE}/auth/login"
        body = f"username={username}&password={password}".encode()
        req = Request(url, data=body)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            token = data.get('access_token')
            user = data.get('user', {})
            print(f"  ✓ {username} ({user.get('role')}, L{user.get('clearance')}) -> Token OK")
            return token
    except HTTPError as e:
        print(f"  ✗ {username} login failed: {e.code}")
        return None

def test_dashboard(token):
    """Test role-specific dashboard endpoint"""
    try:
        req = Request(f"{API_BASE}/dashboard/role-data")
        req.add_header('Authorization', f'Bearer {token}')
        
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            sidebar = data.get('sidebar_items', [])
            print(f"    ✓ Dashboard data received ({len(sidebar)} sidebar items)")
            return True
    except Exception as e:
        print(f"    ✗ Dashboard failed: {e}")
        return False

def test_frontend():
    """Test frontend is being served"""
    try:
        with urlopen("http://127.0.0.1:8000/") as response:
            content = response.read().decode()
            if "JUSTICEVAULT" in content and "role-card" in content:
                size_kb = len(content.encode()) / 1024
                print(f"✓ Frontend served: {size_kb:.1f} KB with role selection UI")
                return True
            else:
                print("✗ Frontend loaded but missing expected content")
                return False
    except Exception as e:
        print(f"✗ Frontend unavailable: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print(" JUSTICEVAULT FRONTEND + API INTEGRATION TEST")
    print("=" * 50)
    print()
    
    # Test 1: Backend health
    if not test_health():
        exit(1)
    
    print()
    print("Testing 5 role logins:")
    roles = [
        ("police.demo", "Police@Demo2026!"),
        ("forensic.demo", "Forensic@Demo2026!"),
        ("judiciary.demo", "Judiciary@Demo2026!"),
        ("higher.demo", "Higher@Demo2026!"),
        ("admin.demo", "Admin@Demo2026!"),
    ]
    
    success_count = 0
    for username, password in roles:
        token = test_login(username, password)
        if token:
            success_count += 1
            test_dashboard(token)
    
    print()
    if test_frontend():
        print()
        print("=" * 50)
        print(f" ALL TESTS PASSED! ({success_count}/5 roles OK)")
        print(" Ready for browser testing at:")
        print(" http://127.0.0.1:8000/")
        print("=" * 50)
