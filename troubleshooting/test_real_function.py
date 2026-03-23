#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from searchEPUB import export_alfred_books_overview
import json

# Test with mock results
test_results = [
    {
        'book_title': 'Test Book One',
        'context': 'This is some test context from the first book',
        'match_text': 'test',
        'location': 'Chapter 1'
    },
    {
        'book_title': 'Test Book One', 
        'context': 'Another test match in the same book',
        'match_text': 'test',
        'location': 'Chapter 2'
    },
    {
        'book_title': 'Another Test Book',
        'context': 'Different book with test content',
        'match_text': 'test', 
        'location': 'Page 5'
    }
]

# Test with completed progress info (this should show summary)
progress_info = {
    'is_complete': True,
    'processed_books': 2,
    'total_books': 2
}

print("Testing export_alfred_books_overview with results and completed progress...")
output = export_alfred_books_overview(test_results, "test", progress_info)
parsed = json.loads(output)

print(f"Number of items returned: {len(parsed['items'])}")
for i, item in enumerate(parsed['items']):
    print(f"{i+1}. UID: {item.get('uid', 'NO_UID')} | Title: {item.get('title', 'NO_TITLE')}")

print(f"\nFull JSON output:")
print(output)