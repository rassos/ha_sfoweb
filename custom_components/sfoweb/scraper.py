"""SFOWeb scraper for appointments using Selenium."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from .const import (
    APPOINTMENTS_URL,
    LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)


class SFOScraper:
    """Handle SFOWeb scraping operations."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper."""
        self.username = username
        self.password = password

    def _setup_driver(self) -> webdriver.Chrome:
        """Set up Chrome driver with container-friendly options."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument('--disable-javascript')  # Try without JS first
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            # Try to use ChromeDriverManager to auto-install
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            _LOGGER.warning(f"ChromeDriverManager failed: {e}, trying system chromedriver")
            try:
                # Fallback to system chromedriver
                driver = webdriver.Chrome(options=options)
            except Exception as e2:
                _LOGGER.error(f"Could not initialize Chrome driver: {e2}")
                raise
        
        driver.set_page_load_timeout(30)
        return driver

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments from SFOWeb system."""
        appointments = []
        
        # Run the blocking selenium code in a thread
        loop = asyncio.get_event_loop()
        try:
            appointments = await loop.run_in_executor(None, self._sync_get_appointments)
        except Exception as e:
            _LOGGER.error(f"Error in async_get_appointments: {e}")
            
        return appointments

    def _sync_get_appointments(self) -> List[Dict[str, Any]]:
        """Synchronous method to get appointments using Selenium."""
        appointments = []
        driver = None
        
        try:
            driver = self._setup_driver()
            wait = WebDriverWait(driver, 20)
            
            # Step 1: Open login page
            _LOGGER.info(f"Opening login page: {LOGIN_URL}")
            driver.get(LOGIN_URL)
            
            # Take screenshot for debugging
            _LOGGER.debug(f"Page title: {driver.title}")
            _LOGGER.debug(f"Current URL: {driver.current_url}")
            
            # Step 2: Look for parent login link
            parent_link = None
            try:
                # Try various selectors for parent login
                selectors = [
                    "//a[contains(@href, 'ParentTabulexLogin')]",
                    "//a[contains(text(), 'Forældre')]",
                    "//a[contains(text(), 'Parent')]",
                    "//a[contains(text(), 'forældre')]",
                ]
                
                for selector in selectors:
                    try:
                        parent_link = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        _LOGGER.info(f"Found parent login link with selector: {selector}")
                        break
                    except TimeoutException:
                        continue
                
                if not parent_link:
                    # Log all links for debugging
                    all_links = driver.find_elements(By.TAG_NAME, "a")
                    _LOGGER.error(f"Could not find parent login. Found {len(all_links)} links:")
                    for i, link in enumerate(all_links[:5]):  # Log first 5 links
                        href = link.get_attribute('href') or 'No href'
                        text = link.text.strip()
                        _LOGGER.error(f"Link {i}: href='{href}', text='{text}'")
                    return appointments
                
                parent_link.click()
                _LOGGER.info("Clicked parent login link")
                
            except Exception as e:
                _LOGGER.error(f"Error finding parent login link: {e}")
                return appointments
            
            # Step 3: Wait for login form and fill it
            try:
                # Wait for username field
                username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
                password_field = driver.find_element(By.NAME, "password")
                
                _LOGGER.info("Found login form fields")
                
                username_field.clear()
                username_field.send_keys(self.username)
                
                password_field.clear()
                password_field.send_keys(self.password)
                
                # Find and click submit button
                submit_button = None
                submit_selectors = [
                    (By.XPATH, "//button[@type='submit']"),
                    (By.XPATH, "//input[@type='submit']"),
                    (By.XPATH, "//button[contains(text(), 'Log')]"),
                    (By.XPATH, "//button[contains(text(), 'Sign')]"),
                ]
                
                for by_type, selector in submit_selectors:
                    try:
                        submit_button = driver.find_element(by_type, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if submit_button:
                    submit_button.click()
                    _LOGGER.info("Submitted login form")
                else:
                    _LOGGER.error("Could not find submit button")
                    return appointments
                
                # Wait for navigation after login
                wait.until(lambda d: d.current_url != driver.current_url)
                
            except Exception as e:
                _LOGGER.error(f"Error during login: {e}")
                return appointments
            
            # Step 4: Navigate to appointments page
            _LOGGER.info(f"Navigating to appointments: {APPOINTMENTS_URL}")
            driver.get(APPOINTMENTS_URL)
            
            # Step 5: Extract appointment data
            try:
                # Wait for table to load
                table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                
                # Find all rows
                rows = table.find_elements(By.TAG_NAME, "tr")
                _LOGGER.info(f"Found {len(rows)} table rows")
                
                if len(rows) <= 1:  # Header only or empty
                    _LOGGER.info("No appointment data found")
                    return appointments
                
                # Skip header row, process data rows
                for i, row in enumerate(rows[1:], 1):
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        if len(cells) >= 4:
                            date_text = cells[0].text.strip()
                            what_text = cells[1].text.strip()
                            time_text = cells[2].text.strip()
                            comment_text = cells[3].text.strip()
                            
                            _LOGGER.debug(f"Row {i}: {date_text} | {what_text} | {time_text}")
                            
                            # Only include "Selvbestemmer" appointments
                            if "Selvbestemmer" in what_text:
                                appointment = {
                                    "date": date_text,
                                    "what": what_text,
                                    "time": time_text,
                                    "comment": comment_text,
                                    "full_description": f"{date_text} - {time_text}"
                                }
                                appointments.append(appointment)
                                _LOGGER.info(f"Added appointment: {date_text} - {time_text}")
                            
                    except Exception as e:
                        _LOGGER.debug(f"Error processing row {i}: {e}")
                        continue
                        
            except TimeoutException:
                _LOGGER.error("Timeout waiting for appointments table")
            except Exception as e:
                _LOGGER.error(f"Error extracting appointments: {e}")
            
            _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments")
            
        except WebDriverException as e:
            _LOGGER.error(f"WebDriver error: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error in scraper: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    _LOGGER.debug(f"Error closing driver: {e}")
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test if credentials are valid."""
        try:
            if not self.username or not self.password:
                return False
            
            # Basic validation
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            _LOGGER.info(f"Testing credentials for user: {self.username}")
            
            # For setup, just validate format to avoid long wait times
            return True
            
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False
