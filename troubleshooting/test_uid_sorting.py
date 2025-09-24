#!/usr/bin/env python3
import json
import hashlib

# Test actual UID sorting behavior
test_items = []

# Summary item
test_items.append({
    "uid": "0-summary",
    "title": "🔍 Summary",
    "subtitle": "This should be first"
})

# Book items (simulate actual book UIDs)
book_titles = ["A Tale of Two Cities", "Moby Dick", "Pride and Prejudice"]
for book_title in book_titles:
    stable_uid = f"book-{hashlib.md5(book_title.encode()).hexdigest()[:8]}"
    test_items.append({
        "uid": stable_uid,
        "title": book_title,
        "subtitle": f"UID: {stable_uid}"
    })

# Sort by UID (how Alfred would sort)
sorted_items = sorted(test_items, key=lambda x: x["uid"])

print("Items sorted by UID:")
for i, item in enumerate(sorted_items, 1):
    print(f"{i}. UID: '{item['uid']}' -> {item['title']}")

# Test different UID prefixes
print("\nTesting different UID prefixes:")
prefixes = ["0-summary", "00-summary", "!summary", "_summary", "aaa-summary"]
for prefix in prefixes:
    test_uid = prefix
    sample_book_uid = f"book-{hashlib.md5('test book'.encode()).hexdigest()[:8]}"
    if test_uid < sample_book_uid:
        print(f"✓ '{test_uid}' sorts before '{sample_book_uid}'")
    else:
        print(f"✗ '{test_uid}' sorts after '{sample_book_uid}'")