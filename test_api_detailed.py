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

if login_response.ok:
    token_data = login_response.json()
    token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test get documents
    print("Fetching documents...")
    docs_response = requests.get(f"{BASE_URL}/documents", headers=headers)
    
    if docs_response.ok:
        docs = docs_response.json()
        
        # Find groups and their version counts
        groups = {}
        for doc in docs:
            group_id = doc.get("document_group_id")
            if group_id:
                if group_id not in groups:
                    groups[group_id] = []
                groups[group_id].append(doc)
        
        print(f"Found {len(groups)} document groups")
        
        # Find a group with multiple versions
        for group_id, group_docs in sorted(groups.items(), key=lambda x: -len(x[1])):
            print(f"\nGroup {group_id}: {len(group_docs)} versions")
            
            if len(group_docs) >= 2:
                # This is a good group for testing
                print(f"  Testing this group with {len(group_docs)} versions:")
                
                # Fetch via API to get full data
                group_response = requests.get(
                    f"{BASE_URL}/documents/group/{group_id}",
                    headers=headers
                )
                if group_response.ok:
                    versions = group_response.json()
                    for i, v in enumerate(versions):
                        has_markdown = bool(v.get("markdown_content"))
                        content_len = len(v.get("markdown_content", ""))
                        print(f"    [{i}] {v['version']} (status={v['status']}, markdown={content_len} chars)")
                    
                    if len(versions) >= 2:
                        # Test diff endpoint
                        v1 = versions[0]
                        v2 = versions[1]
                        print(f"\n  Testing diff between {v1['version']} and {v2['version']}:")
                        
                        diff_response = requests.get(
                            f"{BASE_URL}/documents/{v2['id']}/diff/{v1['id']}",
                            headers=headers
                        )
                        print(f"  Diff Status: {diff_response.status_code}")
                        if diff_response.ok:
                            diff_data = diff_response.json()
                            if isinstance(diff_data, list):
                                added = sum(1 for d in diff_data if d.get("type") == "added")
                                removed = sum(1 for d in diff_data if d.get("type") == "removed")
                                same = sum(1 for d in diff_data if d.get("type") == "same")
                                print(f"    Diff lines: +{added} -{removed} ={same}")
                            else:
                                print(f"    Diff data: {diff_data}")
                        else:
                            print(f"    Error: {diff_response.text}")
                
                # Only test the first group with multiple versions
                break
else:
    print(f"Login Error: {login_response.text}")
