#!/usr/bin/env python3

# Simple test: call searchEPUB.py with test arguments and see what we get
import subprocess
import json
import sys
import os

# Change to the correct directory 
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("Testing searchEPUB.py with mock arguments...")

# Test 1: Call with no books (should trigger our folder search path)
try:
    # This should trigger the path we just fixed 
    result = subprocess.run([
        'python3', 'searchEPUB.py', 
        '--alfred-format',
        'test'  # search term
    ], capture_output=True, text=True, timeout=10)
    
    print(f"Return code: {result.returncode}")
    print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
            print(f"\nParsed JSON structure:")
            print(f"Number of items: {len(parsed.get('items', []))}")
            for i, item in enumerate(parsed.get('items', [])):
                print(f"{i+1}. UID: {item.get('uid', 'NO_UID')} | Title: {item.get('title', 'NO_TITLE')}")
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            
except subprocess.TimeoutExpired:
    print("Command timed out")
except Exception as e:
    print(f"Error running command: {e}")