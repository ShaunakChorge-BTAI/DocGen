#!/usr/bin/env python
import requests
import json

BASE_URL = "http://localhost:8000"

# Test login
print("Testing login...")
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": "suraj@osourceglobal.com", "password": "abcd123"}
)
print(f"Login Status: {login_response.status_code}")
if login_response.ok:
    token_data = login_response.json()
    print(f"Token received: {token_data}")
    token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test get documents
    print("\nFetching documents...")
    docs_response = requests.get(
        f"{BASE_URL}/documents",
        headers=headers
    )
    print(f"Documents Status: {docs_response.status_code}")
    if docs_response.ok:
        docs = docs_response.json()
        print(f"Found {len(docs)} documents")
        if docs:
            doc_with_group = next((d for d in docs if d.get("document_group_id")), None)
            if doc_with_group:
                group_id = doc_with_group["document_group_id"]
                print(f"\nTesting group endpoint with group_id: {group_id}")
                
                # Test get document group
                group_response = requests.get(
                    f"{BASE_URL}/documents/group/{group_id}",
                    headers=headers
                )
                print(f"Group Status: {group_response.status_code}")
                if group_response.ok:
                    versions = group_response.json()
                    print(f"Found {len(versions)} versions in group")
                    for v in versions:
                        has_content = bool(v.get("markdown_content"))
                        print(f"  - {v['version']}: status={v['status']}, has_markdown={has_content}")
                else:
                    print(f"Error: {group_response.text}")
            else:
                print("No documents with group_id found")
    else:
        print(f"Error: {docs_response.text}")
else:
    print(f"Login Error: {login_response.text}")
