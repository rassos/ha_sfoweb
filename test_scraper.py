#!/usr/bin/env python3
"""Test script for the JavaScript-enabled SFO scraper."""

import asyncio
import logging
import sys
import os

# Add the custom_components path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'sfoweb'))

from scraper_enhanced import SFOEnhancedScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_scraper():
    """Test the scraper with dummy credentials."""
    print("Testing SFO Enhanced Scraper...")
    
    # Use dummy credentials for testing (replace with real ones)
    scraper = SFOEnhancedScraper("test_user", "test_pass")
    
    try:
        print("1. Testing credential validation...")
        creds_valid = await scraper.async_test_credentials()
        print(f"   Credential test result: {creds_valid}")
        
        print("2. Testing appointment fetching...")
        appointments = await scraper.async_get_appointments()
        print(f"   Found {len(appointments)} appointments")
        
        for i, appointment in enumerate(appointments[:3], 1):  # Show first 3
            print(f"   Appointment {i}: {appointment.get('full_description', 'No description')}")
        
        print("Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

if __name__ == "__main__":
    print("SFO Enhanced Scraper Test")
    print("========================")
    print("Note: This will use dummy credentials and likely fail authentication,")
    print("but it will test the basic functionality and import structure.")
    print()
    
    success = asyncio.run(test_scraper())
    
    if success:
        print("\n✅ Basic test passed - scraper structure is working")
    else:
        print("\n❌ Test failed - check the error messages above")