"""SFOWeb scraper for appointments using Playwright with container support."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any, Dict, List

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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
        self._browser_installed = False

    async def _ensure_browser_installed(self) -> bool:
        """Ensure Playwright browser is installed."""
        if self._browser_installed:
            return True
            
        try:
            # Install chromium browser for Playwright
            _LOGGER.info("Installing Playwright browser...")
            
            # Run playwright install command
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "playwright", "install", "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                _LOGGER.info("Playwright browser installed successfully")
                self._browser_installed = True
                return True
            else:
                _LOGGER.error(f"Failed to install Playwright browser: {stderr.decode()}")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Error installing Playwright browser: {e}")
            return False

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments from SFOWeb system."""
        appointments = []
        
        try:
            # Ensure browser is installed
            if not await self._ensure_browser_installed():
                _LOGGER.error("Could not install Playwright browser")
                return appointments
            
            async with async_playwright() as p:
                # Launch browser with container-friendly options
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )

                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )

                page = await context.new_page()

                # Step 1: Open selector page
                _LOGGER.info(f"Opening login page: {LOGIN_URL}")
                await page.goto(LOGIN_URL, wait_until="networkidle")

                # Step 2: Click the "Forældre Login"
                try:
                    _LOGGER.info("Looking for parent login link...")
                    
                    # Wait a bit for dynamic content to load
                    await page.wait_for_timeout(2000)
                    
                    # Try multiple selectors for the parent login
                    parent_selectors = [
                        'a[href*="ParentTabulexLogin"]',
                        'a:has-text("Forældre")',
                        'a:has-text("Parent")',
                        'a:has-text("forældre")'
                    ]
                    
                    parent_clicked = False
                    for selector in parent_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                _LOGGER.info(f"Found parent login with selector: {selector}")
                                await element.click()
                                parent_clicked = True
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Selector {selector} failed: {e}")
                            continue
                    
                    if not parent_clicked:
                        _LOGGER.error("Could not find parent login link")
                        await browser.close()
                        return appointments
                        
                    await page.wait_for_load_state("networkidle")
                    
                except Exception as e:
                    _LOGGER.error(f"Error clicking parent login: {e}")
                    await browser.close()
                    return appointments

                # Step 3: Login
                try:
                    _LOGGER.info("Attempting to login...")
                    
                    # Wait for login form to appear
                    await page.wait_for_timeout(2000)
                    
                    # Try multiple selectors for username field
                    username_selectors = [
                        'input#username',
                        'input[name="username"]',
                        'input[type="text"]',
                        'input[placeholder*="bruger"]',
                        'input[placeholder*="email"]'
                    ]
                    
                    username_filled = False
                    for selector in username_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                _LOGGER.info(f"Found username field with selector: {selector}")
                                await element.fill(self.username)
                                username_filled = True
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Username selector {selector} failed: {e}")
                            continue
                    
                    if not username_filled:
                        _LOGGER.error("Could not find username field")
                        await browser.close()
                        return appointments
                    
                    # Try multiple selectors for password field
                    password_selectors = [
                        'input#password',
                        'input[name="password"]',
                        'input[type="password"]'
                    ]
                    
                    password_filled = False
                    for selector in password_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                _LOGGER.info(f"Found password field with selector: {selector}")
                                await element.fill(self.password)
                                password_filled = True
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Password selector {selector} failed: {e}")
                            continue
                    
                    if not password_filled:
                        _LOGGER.error("Could not find password field")
                        await browser.close()
                        return appointments
                    
                    # Submit the form
                    submit_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button:has-text("Log")',
                        'button:has-text("Sign")',
                        '.login-button',
                        '#login-submit'
                    ]
                    
                    submit_clicked = False
                    for selector in submit_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                _LOGGER.info(f"Found submit button with selector: {selector}")
                                await element.click()
                                submit_clicked = True
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Submit selector {selector} failed: {e}")
                            continue
                    
                    if not submit_clicked:
                        _LOGGER.error("Could not find submit button")
                        await browser.close()
                        return appointments
                    
                    # Wait for navigation after login
                    await page.wait_for_load_state("networkidle")
                    
                except Exception as e:
                    _LOGGER.error(f"Error during login: {e}")
                    await browser.close()
                    return appointments

                # Step 4: Go to appointments page
                _LOGGER.info(f"Navigating to appointments page: {APPOINTMENTS_URL}")
                await page.goto(APPOINTMENTS_URL, wait_until="networkidle")
                await page.wait_for_timeout(2000)  # Give JS some breathing room
                
                # Step 5: Extract data from the appointments table
                try:
                    # Wait for table to load
                    await page.wait_for_timeout(3000)
                    
                    # Try multiple selectors for the appointments table
                    table_selectors = [
                        'table.table-striped tbody tr',
                        'table tbody tr',
                        '.appointments tr',
                        '[data-table] tr'
                    ]
                    
                    rows = None
                    for selector in table_selectors:
                        try:
                            rows = page.locator(selector)
                            row_count = await rows.count()
                            if row_count > 0:
                                _LOGGER.info(f"Found {row_count} rows with selector: {selector}")
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Table selector {selector} failed: {e}")
                            continue
                    
                    if not rows or await rows.count() == 0:
                        _LOGGER.warning("No appointment rows found")
                        await browser.close()
                        return appointments
                    
                    row_count = await rows.count()
                    
                    # Check if appointments exist
                    if row_count == 1:
                        first_row_text = await rows.first.inner_text()
                        if "Der er ingen aktive" in first_row_text:
                            _LOGGER.info("No active appointments found")
                            await browser.close()
                            return appointments

                    # Extract appointment data
                    for i in range(row_count):
                        try:
                            row = rows.nth(i)
                            cells = row.locator('td')
                            cell_count = await cells.count()
                            
                            if cell_count >= 4:  # Ensure we have at least the required columns
                                date_text = (await cells.nth(0).inner_text()).strip()
                                what_text = (await cells.nth(1).inner_text()).strip()
                                time_text = (await cells.nth(2).inner_text()).strip()
                                comment_text = (await cells.nth(3).inner_text()).strip()
                                
                                _LOGGER.debug(f"Row {i}: {date_text} | {what_text} | {time_text}")
                                
                                # Only include "Selvbestemmer" appointments
                                if "Selvbestemmer" in what_text:
                                    appointments.append({
                                        "date": date_text,
                                        "what": what_text,
                                        "time": time_text,
                                        "comment": comment_text,
                                        "full_description": f"{date_text} - {time_text}"
                                    })
                                    _LOGGER.info(f"Found appointment: {date_text} - {time_text}")
                        except Exception as e:
                            _LOGGER.debug(f"Error processing row {i}: {e}")
                            continue

                except Exception as e:
                    _LOGGER.error(f"Error extracting appointments: {e}")

                await browser.close()
                
                _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments")
                return appointments

        except PlaywrightTimeoutError as e:
            _LOGGER.error(f"Timeout error while scraping SFOWeb: {e}")
            return appointments
        except Exception as e:
            _LOGGER.error(f"Unexpected error while scraping SFOWeb: {e}")
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
            # Real validation happens during data fetch
            return True
            
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False
