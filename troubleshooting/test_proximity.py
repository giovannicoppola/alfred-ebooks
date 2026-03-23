#!/usr/bin/env python3

# Test proximity search functionality
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test the proximity search functions directly
def test_proximity_functions():
    # Mock imports to avoid dependency issues
    try:
        from searchEPUB import is_proximity_search, simple_tokenize, find_proximity_matches
    except ImportError as e:
        print(f"Import error: {e}")
        return
    
    print("Testing proximity search functions...")
    
    # Test 1: is_proximity_search
    print("\n1. Testing is_proximity_search:")
    test_cases = [
        ("love death", True),
        ("love", False),  
        ("love death war", False),
        ("  love   death  ", True),
        ("machine learning", True)
    ]
    
    for text, expected in test_cases:
        result = is_proximity_search(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' -> {result} (expected: {expected})")
    
    # Test 2: simple_tokenize
    print("\n2. Testing simple_tokenize:")
    test_text = "The king fought in the great battle for peace."
    tokens, positions = simple_tokenize(test_text)
    print(f"  Text: '{test_text}'")
    print(f"  Tokens: {tokens[:5]}...")  # Show first 5
    print(f"  Positions: {positions[:5]}...")
    
    # Test 3: find_proximity_matches
    print("\n3. Testing find_proximity_matches:")
    test_text = "The king was brave. He fought many battles. The great king won the final battle against his enemies."
    matches = find_proximity_matches(test_text, "king", "battle", max_distance=10)
    
    print(f"  Text: '{test_text}'")
    print(f"  Searching for 'king' within 10 words of 'battle'")
    print(f"  Found {len(matches)} matches:")
    
    for i, (start, end, context, distance) in enumerate(matches, 1):
        print(f"    {i}. Distance: {distance} words")
        print(f"       Context: '{context[:60]}...'")

if __name__ == "__main__":
    test_proximity_functions()