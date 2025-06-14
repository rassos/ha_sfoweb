#!/usr/bin/env python3
"""Test script for the enhanced SFO scraper."""

import asyncio
import logging
import sys
import os
import getpass

# Add the custom_components path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from sfoweb.scraper_enhanced import SFOEnhancedScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_credentials():
    """Prompt user for credentials."""
    print("Please enter your SFO credentials:")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ").strip()
    
    if not username or not password:
        print("❌ Both username and password are required!")
        return None, None
    
    return username, password

async def test_scraper():
    """Test the scraper with user-provided credentials."""
    print("Testing SFO Enhanced Scraper...")
    
    # Get credentials from user
    username, password = get_credentials()
    if not username or not password:
        return False
    
    scraper = SFOEnhancedScraper(username, password)
    
    try:
        print("1. Testing credential validation...")
        creds_valid = await scraper.async_test_credentials()
        print(f"   Credential test result: {creds_valid}")
        
        print("2. Testing appointment fetching...")
        appointments = await scraper.async_get_appointments()
        print(f"   Found {len(appointments)} appointments")
        
        for i, appointment in enumerate(appointments[:3], 1):  # Show first 3
            print(f"   Appointment {i}: {appointment.get('full_description', 'No description')}")
        
        print("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    print("SFO Enhanced Scraper Test")
    print("========================")
    print("This will test the scraper with your actual SFO credentials.")
    print("Your credentials will not be stored or transmitted anywhere.")
    print()
    
    success = asyncio.run(test_scraper())
    
    if success:
        print("\n🎉 Test passed - scraper is working with your credentials!")
    else:
        print("\n💥 Test failed - check the error messages above")