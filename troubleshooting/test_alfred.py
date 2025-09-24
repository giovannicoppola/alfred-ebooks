#!/usr/bin/env python3

import sys
import json

# Simple test for Alfred - just output basic JSON
alfred_json = {
    "items": [
        {
            "uid": "test-item",
            "title": "🔍 Test Alfred Output",
            "subtitle": "This is a test to see if Alfred can see our output",
            "icon": {"path": "icon.png"},
            "valid": True,
            "arg": "test-argument"
        }
    ]
}

# Output JSON exactly like the real script
sys.stdout.write(json.dumps(alfred_json, indent=2, ensure_ascii=False) + '\n')
sys.stdout.flush()

# Debug to stderr
print("[DEBUG] Test script completed", file=sys.stderr)