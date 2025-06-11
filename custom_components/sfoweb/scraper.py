"""SFOWeb scraper for appointments."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .const import (
    APPOINTMENTS_TABLE_SELECTOR,
    APPOINTMENTS_URL,
    LOGIN_URL,
    PARENT_LOGIN_SELECTOR,
    PASSWORD_SELECTOR,
    SUBMIT_SELECTOR,
    USERNAME_SELECTOR,
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
        appointments = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )

                page = await context.new_page()

                # Step 1: Open selector page
                await page.goto(LOGIN_URL)
                await page.wait_for_load_state("networkidle")

                # Step 2: Click the "Forældre Login"
                await page.click(PARENT_LOGIN_SELECTOR)
                await page.wait_for_load_state("networkidle")

                # Step 3: Login
                await page.wait_for_selector(USERNAME_SELECTOR, timeout=15000)
                await page.fill(USERNAME_SELECTOR, self.username)
                await page.fill(PASSWORD_SELECTOR, self.password)
                await page.click(SUBMIT_SELECTOR)

                # Step 4: Go to appointments page
                await page.wait_for_load_state("networkidle")
                await page.goto(APPOINTMENTS_URL)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)  # Give JS some breathing room
                
                # Step 5: Extract data from the appointments table
                rows = page.locator(APPOINTMENTS_TABLE_SELECTOR)
                row_count = await rows.count()
                
                # Check if appointments exist
                if row_count == 0:
                    _LOGGER.info("No appointment rows found")
                elif row_count == 1:
                    first_row_text = await rows.first.inner_text()
                    if "Der er ingen aktive" in first_row_text:
                        _LOGGER.info("No active appointments found")
                        await browser.close()
                        return appointments

                # Extract appointment data
                for i in range(row_count):
                    row = rows.nth(i)
                    cells = row.locator('td')
                    cell_count = await cells.count()
                    
                    if cell_count >= 4:  # Ensure we have at least the required columns
                        date_text = (await cells.nth(0).inner_text()).strip()
                        what_text = (await cells.nth(1).inner_text()).strip()
                        time_text = (await cells.nth(2).inner_text()).strip()
                        comment_text = (await cells.nth(3).inner_text()).strip()
                        
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

                await browser.close()
                
                _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments")
                return appointments

        except PlaywrightTimeoutError as e:
            _LOGGER.error(f"Timeout error while scraping SFOWeb: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error while scraping SFOWeb: {e}")
            raise
