#!/usr/bin/env python3
"""
Test script to verify all Alfred workflow dependencies work correctly.
"""
import sys
import os

# Add the lib directory to Python path (same as Alfred workflow does)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

def test_imports():
    """Test all critical imports for the Alfred workflow."""
    try:
        # Test lxml (the problematic one)
        from lxml import etree
        print("✅ lxml.etree import successful")
        
        # Test ebooklib
        from ebooklib import epub
        print("✅ ebooklib import successful")
        
        # Test other dependencies
        from bs4 import BeautifulSoup
        print("✅ beautifulsoup4 import successful")
        
        import requests
        print("✅ requests import successful")
        
        import biplist
        print("✅ biplist import successful")
        
        import xmltodict
        print("✅ xmltodict import successful")
        
        from docopt import docopt
        print("✅ docopt import successful")
        
        print("\n🎉 All imports successful! The Alfred workflow should work now.")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    print(f"Testing with Python {sys.version}")
    print(f"Python executable: {sys.executable}")
    print("-" * 50)
    
    success = test_imports()
    sys.exit(0 if success else 1)