"""
test_managefilesearchstore.py

Test script to validate the Gemini File Search Store creation and update logic.
Ensure you have set the GEMINI_API_KEY environment variable and authenticated
with Google Cloud (e.g., `gcloud auth application-default login`) before running.

Usage:
    python test_managefilesearchstore.py
"""

import os
import sys

# Import the methods from your renamed module
try:
    from managefilesearchstore import create_agent_file_search, update_agent_file_search
except ImportError:
    print("Error: Could not import 'managefilesearchstore'.")
    print("Ensure 'managefilesearchstore.py' is in the same directory as this script.")
    sys.exit(1)

def run_tests():
    agent_name = "FARAH"
    
    # Pre-flight check for Gemini API Key
    if "GEMINI_API_KEY" not in os.environ:
        print("⚠️  WARNING: GEMINI_API_KEY environment variable is not set.")
        print("Please set it using: export GEMINI_API_KEY='your_key_here'")
        sys.exit(1)

    print("="*60)
    print(f"🧪 Starting Tests for Agent: {agent_name}")
    print("="*60)

    # ---------------------------------------------------------
    # TEST 1: Create File Search Store
    # ---------------------------------------------------------
    print("\n[TEST 1] Testing create_agent_file_search()...")
    try:
        store_1 = create_agent_file_search(agent_name)
        print("\n✅ TEST 1 PASSED: Successfully created File Search Store!")
        print(f"Store Name: {store_1.name}")
        print(f"Store Display Name: {store_1.display_name}")
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {str(e)}")
        # If creation fails, we might still want to try update if it already existed
        # but usually, we'd stop here. For testing, we will proceed.

    print("-" * 60)

    # ---------------------------------------------------------
    # TEST 2: Update File Search Store (Delete & Recreate)
    # ---------------------------------------------------------
    print("\n[TEST 2] Testing update_agent_file_search()...")
    try:
        store_2 = update_agent_file_search(agent_name)
        print("\n✅ TEST 2 PASSED: Successfully updated File Search Store!")
        print(f"New Store Name: {store_2.name}")
        print(f"New Store Display Name: {store_2.display_name}")
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {str(e)}")

    print("\n" + "="*60)
    print("🏁 Tests completed.")
    print("="*60)

if __name__ == "__main__":
    run_tests()