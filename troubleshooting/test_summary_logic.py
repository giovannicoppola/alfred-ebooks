#!/usr/bin/env python3

# Quick test to see if the summary logic works
import json
import hashlib

# Simulate the exact conditions from searchEPUB.py
results = [
    {'book_title': 'Test Book', 'context': 'some test context'},
    {'book_title': 'Another Book', 'context': 'more context'}
]
search_text = "test"
progress_info = {
    'processed_books': 2,
    'total_books': 2,
    'current_book': 'Complete',
    'is_complete': True
}

# Mirror the exact logic from export_alfred_books_overview
alfred_json = {
    "items": []
}
alfred_items = alfred_json["items"]

# Group results by book
books = {}
total_matches = len(results)
for result in results:
    book_title = result['book_title']
    if book_title not in books:
        books[book_title] = []
    books[book_title].append(result)

# Summary item always at the top when search is complete
summary_item = None
print(f"progress_info: {progress_info}")
print(f"progress_info.get('is_complete', False): {progress_info.get('is_complete', False)}")

if progress_info and progress_info.get('is_complete', False):
    summary_item = {
        "uid": "0-summary",
        "title": f"🔍 Search Results for '{search_text}'",
        "subtitle": f"Found {total_matches} total matches across {len(books)} books",
        "icon": {"path": "icon.png"},
        "valid": False
    }
    print(f"Created summary_item: {summary_item}")

# Add book items
for book_index, (book_title, book_results) in enumerate(books.items(), 1):
    match_count = len(book_results)
    stable_uid = f"book-{hashlib.md5(book_title.encode()).hexdigest()[:8]}"
    alfred_items.append({
        "uid": stable_uid,
        "title": f"{book_index}. {book_title}",
        "subtitle": f"{match_count} matches",
        "icon": {"path": "icon.png"},
        "valid": True
    })

# Ensure summary item is always first when search is complete
if summary_item:
    alfred_items.insert(0, summary_item)
    print(f"Inserted summary at position 0")

print(f"\nFinal alfred_items order:")
for i, item in enumerate(alfred_items):
    print(f"{i}: {item['uid']} - {item['title']}")

# Test the JSON output
final_json = json.dumps(alfred_json, indent=2, ensure_ascii=False)
print(f"\nFinal JSON structure:")
print(final_json)