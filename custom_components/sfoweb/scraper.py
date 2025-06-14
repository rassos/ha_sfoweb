"""SFOWeb scraper for appointments using aiohttp and BeautifulSoup."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List
import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime

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
        appointments = []
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Step 1: Get the main login page to establish session
                _LOGGER.debug("Getting main login page")
                async with session.get(LOGIN_URL) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load login page: {response.status}")
                        return appointments
                    
                    login_html = await response.text()
                    soup = BeautifulSoup(login_html, 'html.parser')
                
                # Step 2: Find and click the "Forældre Login" link
                parent_login_link = soup.find('a', href=lambda x: x and 'ParentTabulexLogin' in x)
                if not parent_login_link:
                    _LOGGER.error("Could not find parent login link")
                    return appointments
                
                parent_login_url = parent_login_link['href']
                if not parent_login_url.startswith('http'):
                    parent_login_url = f"https://sfo-web.aula.dk{parent_login_url}"
                
                _LOGGER.debug(f"Found parent login URL: {parent_login_url}")
                
                # Step 3: Go to parent login page
                async with session.get(parent_login_url) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load parent login page: {response.status}")
                        return appointments
                    
                    parent_login_html = await response.text()
                    login_soup = BeautifulSoup(parent_login_html, 'html.parser')
                
                # Step 4: Find the login form and extract required fields
                login_form = login_soup.find('form')
                if not login_form:
                    _LOGGER.error("Could not find login form")
                    return appointments
                
                form_action = login_form.get('action', '')
                if not form_action.startswith('http'):
                    form_action = f"https://sfo-web.aula.dk{form_action}"
                
                # Prepare login data
                form_data = {
                    'username': self.username,
                    'password': self.password,
                }
                
                # Add any hidden fields
                for hidden_input in login_soup.find_all('input', type='hidden'):
                    name = hidden_input.get('name')
                    value = hidden_input.get('value', '')
                    if name:
                        form_data[name] = value
                
                _LOGGER.debug(f"Submitting login to: {form_action}")
                
                # Step 5: Submit login form
                async with session.post(form_action, data=form_data) as response:
                    if response.status not in [200, 302]:
                        _LOGGER.error(f"Login failed with status: {response.status}")
                        return appointments
                    
                    # Check if we were redirected (successful login usually redirects)
                    final_url = str(response.url)
                    _LOGGER.debug(f"After login, redirected to: {final_url}")
                
                # Step 6: Go to appointments page
                _LOGGER.debug(f"Getting appointments from: {APPOINTMENTS_URL}")
                async with session.get(APPOINTMENTS_URL) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load appointments page: {response.status}")
                        return appointments
                    
                    appointments_html = await response.text()
                    appointments_soup = BeautifulSoup(appointments_html, 'html.parser')
                
                # Step 7: Parse appointments table
                appointments = self._parse_appointments_table(appointments_soup)
                
                _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments for {self.username}")
                return appointments

        except aiohttp.ClientError as e:
            _LOGGER.error(f"Network error while scraping SFOWeb: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error while scraping SFOWeb: {e}")
            raise

    def _parse_appointments_table(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse the appointments table from the HTML."""
        appointments = []
        
        try:
            # Look for the table with appointment data
            table = soup.find('table', class_='table-striped')
            if not table:
                # Try alternative selectors
                table = soup.find('table')
            
            if not table:
                _LOGGER.warning("No appointments table found")
                return appointments
            
            tbody = table.find('tbody')
            if not tbody:
                _LOGGER.warning("No tbody found in appointments table")
                return appointments
            
            rows = tbody.find_all('tr')
            
            if not rows:
                _LOGGER.info("No appointment rows found")
                return appointments
            
            # Check if there's a "no appointments" message
            if len(rows) == 1:
                first_row_text = rows[0].get_text().strip()
                if "Der er ingen aktive" in first_row_text:
                    _LOGGER.info("No active appointments found")
                    return appointments
            
            # Parse each row
            for row in rows:
                cells = row.find_all('td')
                
                if len(cells) >= 4:  # Ensure we have at least the required columns
                    date_text = cells[0].get_text().strip()
                    what_text = cells[1].get_text().strip()
                    time_text = cells[2].get_text().strip()
                    comment_text = cells[3].get_text().strip()
                    
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
            _LOGGER.error(f"Error parsing appointments table: {e}")
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test if credentials are valid by attempting to login."""
        try:
            if not self.username or not self.password:
                return False
            
            # Basic validation
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            # Try to perform actual login test
            timeout = aiohttp.ClientTimeout(total=15)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Get login page
                async with session.get(LOGIN_URL) as response:
                    if response.status != 200:
                        return False
                    
                    login_html = await response.text()
                    soup = BeautifulSoup(login_html, 'html.parser')
                
                # Find parent login link
                parent_login_link = soup.find('a', href=lambda x: x and 'ParentTabulexLogin' in x)
                if not parent_login_link:
                    return False
                
                parent_login_url = parent_login_link['href']
                if not parent_login_url.startswith('http'):
                    parent_login_url = f"https://sfo-web.aula.dk{parent_login_url}"
                
                # Get parent login page
                async with session.get(parent_login_url) as response:
                    if response.status != 200:
                        return False
                    
                    parent_login_html = await response.text()
                    login_soup = BeautifulSoup(parent_login_html, 'html.parser')
                
                # Find login form
                login_form = login_soup.find('form')
                if not login_form:
                    return False
                
                form_action = login_form.get('action', '')
                if not form_action.startswith('http'):
                    form_action = f"https://sfo-web.aula.dk{form_action}"
                
                # Prepare login data
                form_data = {
                    'username': self.username,
                    'password': self.password,
                }
                
                # Add hidden fields
                for hidden_input in login_soup.find_all('input', type='hidden'):
                    name = hidden_input.get('name')
                    value = hidden_input.get('value', '')
                    if name:
                        form_data[name] = value
                
                # Submit login
                async with session.post(form_action, data=form_data) as response:
                    # Check for successful login (usually redirects or shows different page)
                    if response.status in [200, 302]:
                        response_text = await response.text()
                        
                        # Check if login was successful by looking for error messages
                        if "fejl" in response_text.lower() or "error" in response_text.lower():
                            return False
                        
                        # If we can access the appointments page, login was successful
                        try:
                            async with session.get(APPOINTMENTS_URL) as app_response:
                                return app_response.status == 200
                        except:
                            # If we can't access appointments, but login didn't show errors, 
                            # assume credentials are valid
                            return True
                    
                    return False
            
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False
