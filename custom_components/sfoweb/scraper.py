"""SFOWeb scraper for appointments."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

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

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments from SFOWeb system."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_appointments_sync
        )

    def _get_appointments_sync(self) -> List[Dict[str, Any]]:
        """Synchronous appointment fetching."""
        appointments = []
        driver = None
        
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            wait = WebDriverWait(driver, 15)

            # Step 1: Open selector page
            driver.get(LOGIN_URL)

            # Step 2: Click the "Forældre Login"
            parent_login = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href*="ParentTabulexLogin"]'))
            )
            parent_login.click()

            # Step 3: Login
            username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input#username')))
            password_field = driver.find_element(By.CSS_SELECTOR, 'input#password')
            
            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            
            submit_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            submit_button.click()

            # Step 4: Go to appointments page
            driver.get(APPOINTMENTS_URL)
            
            # Wait for page to load
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Step 5: Extract data from the appointments table
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, 'table.table-striped > tbody > tr')
                
                if not rows:
                    _LOGGER.info("No appointment rows found")
                elif len(rows) == 1:
                    first_row_text = rows[0].text
                    if "Der er ingen aktive" in first_row_text:
                        _LOGGER.info("No active appointments found")
                        return appointments

                # Extract appointment data
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    
                    if len(cells) >= 4:  # Ensure we have at least the required columns
                        date_text = cells[0].text.strip()
                        what_text = cells[1].text.strip()
                        time_text = cells[2].text.strip()
                        comment_text = cells[3].text.strip()
                        
                        # Only include "Selvbestemmer" appointments
                        if "Selvbestemmer" in what_text:
                            appointments.append({
                                "date": date_text,
                                "what": what_text,
                                "time": time_text,
                                "comment": comment_text,
                                "full_description": f"{date_text} - {time_text}"
                            })
                            _LOGGER.debug(f"Found appointment: {date_text} - {time_text}")

            except Exception as e:
                _LOGGER.warning(f"Error extracting appointments: {e}")
                
            _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments")
            return appointments

        except TimeoutException as e:
            _LOGGER.error(f"Timeout error while scraping SFOWeb: {e}")
            raise
        except WebDriverException as e:
            _LOGGER.error(f"WebDriver error while scraping SFOWeb: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error while scraping SFOWeb: {e}")
            raise
        finally:
            if driver:
                driver.quit()
