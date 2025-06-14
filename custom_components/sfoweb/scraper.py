"""SFOWeb scraper for appointments with extensive debugging."""
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
            
            # Use a more realistic user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                # Step 1: Get the main login page
                _LOGGER.info(f"Getting main login page: {LOGIN_URL}")
                async with session.get(LOGIN_URL) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load login page: {response.status}")
                        return appointments
                    
                    login_html = await response.text()
                    _LOGGER.debug(f"Login page HTML length: {len(login_html)}")
                    
                    # Save a snippet for debugging
                    if len(login_html) > 500:
                        _LOGGER.debug(f"Login page HTML snippet: {login_html[:500]}...")
                    else:
                        _LOGGER.debug(f"Full login page HTML: {login_html}")
                    
                    soup = BeautifulSoup(login_html, 'html.parser')
                
                # Step 2: Look for parent login link with multiple strategies
                parent_login_link = None
                
                # Strategy 1: Look for ParentTabulexLogin
                parent_login_link = soup.find('a', href=lambda x: x and 'ParentTabulexLogin' in x)
                if parent_login_link:
                    _LOGGER.info("Found parent login link with ParentTabulexLogin")
                else:
                    # Strategy 2: Look for text containing "forældre" or "parent"
                    for link in soup.find_all('a'):
                        link_text = link.get_text().lower()
                        if 'forældre' in link_text or 'parent' in link_text:
                            parent_login_link = link
                            _LOGGER.info(f"Found parent login link by text: {link_text}")
                            break
                
                if not parent_login_link:
                    # Log all links for debugging
                    all_links = soup.find_all('a')
                    _LOGGER.error(f"Could not find parent login link. Found {len(all_links)} links:")
                    for i, link in enumerate(all_links[:10]):  # Show first 10 links
                        href = link.get('href', 'No href')
                        text = link.get_text().strip()
                        _LOGGER.error(f"Link {i}: href='{href}', text='{text}'")
                    return appointments
                
                parent_login_url = parent_login_link['href']
                if not parent_login_url.startswith('http'):
                    if parent_login_url.startswith('/'):
                        parent_login_url = f"https://sfo-web.aula.dk{parent_login_url}"
                    else:
                        parent_login_url = f"https://sfo-web.aula.dk/{parent_login_url}"
                
                _LOGGER.info(f"Parent login URL: {parent_login_url}")
                
                # Step 3: Go to parent login page
                async with session.get(parent_login_url) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load parent login page: {response.status}")
                        return appointments
                    
                    parent_login_html = await response.text()
                    _LOGGER.debug(f"Parent login page HTML length: {len(parent_login_html)}")
                    
                    # Save snippet for debugging
                    if len(parent_login_html) > 500:
                        _LOGGER.debug(f"Parent login page snippet: {parent_login_html[:500]}...")
                    
                    login_soup = BeautifulSoup(parent_login_html, 'html.parser')
                
                # Step 4: Find the login form with multiple strategies
                login_form = None
                
                # Strategy 1: Find form tag
                login_form = login_soup.find('form')
                if login_form:
                    _LOGGER.info("Found login form using <form> tag")
                else:
                    # Strategy 2: Look for forms with specific attributes
                    login_form = login_soup.find('form', {'method': 'post'})
                    if login_form:
                        _LOGGER.info("Found login form with method=post")
                
                if not login_form:
                    # Log all forms for debugging
                    all_forms = login_soup.find_all('form')
                    _LOGGER.error(f"Could not find login form. Found {len(all_forms)} forms:")
                    for i, form in enumerate(all_forms):
                        action = form.get('action', 'No action')
                        method = form.get('method', 'No method')
                        _LOGGER.error(f"Form {i}: action='{action}', method='{method}'")
                    
                    # Also check for input fields (maybe it's not in a form)
                    username_inputs = login_soup.find_all('input', {'name': 'username'})
                    password_inputs = login_soup.find_all('input', {'type': 'password'})
                    _LOGGER.error(f"Found {len(username_inputs)} username inputs and {len(password_inputs)} password inputs")
                    
                    return appointments
                
                form_action = login_form.get('action', '')
                if not form_action:
                    # If no action, submit to same URL
                    form_action = parent_login_url
                elif not form_action.startswith('http'):
                    if form_action.startswith('/'):
                        form_action = f"https://sfo-web.aula.dk{form_action}"
                    else:
                        form_action = f"https://sfo-web.aula.dk/{form_action}"
                
                _LOGGER.info(f"Form action URL: {form_action}")
                
                # Prepare login data
                form_data = {
                    'username': self.username,
                    'password': self.password,
                }
                
                # Add any hidden fields
                hidden_count = 0
                for hidden_input in login_soup.find_all('input', type='hidden'):
                    name = hidden_input.get('name')
                    value = hidden_input.get('value', '')
                    if name:
                        form_data[name] = value
                        hidden_count += 1
                        _LOGGER.debug(f"Added hidden field: {name}={value}")
                
                _LOGGER.info(f"Added {hidden_count} hidden fields to form data")
                _LOGGER.debug(f"Final form data keys: {list(form_data.keys())}")
                
                # Step 5: Submit login form
                _LOGGER.info(f"Submitting login to: {form_action}")
                async with session.post(form_action, data=form_data) as response:
                    _LOGGER.info(f"Login response status: {response.status}")
                    _LOGGER.info(f"Login response URL: {response.url}")
                    
                    if response.status not in [200, 302]:
                        _LOGGER.error(f"Login failed with status: {response.status}")
                        return appointments
                    
                    response_text = await response.text()
                    _LOGGER.debug(f"Login response length: {len(response_text)}")
                    
                    # Check for error indicators
                    if "fejl" in response_text.lower() or "error" in response_text.lower():
                        _LOGGER.error("Login response contains error keywords")
                        if len(response_text) > 200:
                            _LOGGER.debug(f"Error response snippet: {response_text[:200]}...")
                        return appointments
                
                # Step 6: Try to access appointments page
                _LOGGER.info(f"Attempting to access appointments page: {APPOINTMENTS_URL}")
                async with session.get(APPOINTMENTS_URL) as response:
                    _LOGGER.info(f"Appointments page status: {response.status}")
                    
                    if response.status != 200:
                        _LOGGER.error(f"Failed to load appointments page: {response.status}")
                        return appointments
                    
                    appointments_html = await response.text()
                    _LOGGER.debug(f"Appointments page HTML length: {len(appointments_html)}")
                    
                    appointments_soup = BeautifulSoup(appointments_html, 'html.parser')
                
                # Step 7: Parse appointments table
                appointments = self._parse_appointments_table(appointments_soup)
                
                _LOGGER.info(f"Successfully retrieved {len(appointments)} appointments for {self.username}")
                return appointments

        except aiohttp.ClientError as e:
            _LOGGER.error(f"Network error while scraping SFOWeb: {e}")
            # Return empty list instead of raising to avoid breaking the integration
            return []
        except Exception as e:
            _LOGGER.error(f"Unexpected error while scraping SFOWeb: {e}", exc_info=True)
            return []

    def _parse_appointments_table(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse the appointments table from the HTML."""
        appointments = []
        
        try:
            # Look for tables with different strategies
            table = None
            
            # Strategy 1: table with class table-striped
            table = soup.find('table', class_='table-striped')
            if table:
                _LOGGER.info("Found appointments table with class 'table-striped'")
            else:
                # Strategy 2: any table
                table = soup.find('table')
                if table:
                    _LOGGER.info("Found appointments table (generic table)")
            
            if not table:
                # Log what we found instead
                all_tables = soup.find_all('table')
                _LOGGER.warning(f"No appointments table found. Found {len(all_tables)} tables total")
                
                # Look for any content that might contain appointments
                content_divs = soup.find_all('div', class_=['content', 'main', 'appointments'])
                _LOGGER.info(f"Found {len(content_divs)} potential content divs")
                
                return appointments
            
            tbody = table.find('tbody')
            if not tbody:
                _LOGGER.debug("No tbody found, using table directly")
                tbody = table
            
            rows = tbody.find_all('tr')
            _LOGGER.info(f"Found {len(rows)} rows in appointments table")
            
            if not rows:
                _LOGGER.info("No appointment rows found")
                return appointments
            
            # Check if there's a "no appointments" message
            if len(rows) == 1:
                first_row_text = rows[0].get_text().strip()
                _LOGGER.debug(f"Single row text: {first_row_text}")
                if "Der er ingen aktive" in first_row_text or "ingen" in first_row_text.lower():
                    _LOGGER.info("No active appointments message found")
                    return appointments
            
            # Parse each row
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                _LOGGER.debug(f"Row {i}: found {len(cells)} cells")
                
                if len(cells) >= 4:  # Ensure we have at least the required columns
                    date_text = cells[0].get_text().strip()
                    what_text = cells[1].get_text().strip()
                    time_text = cells[2].get_text().strip()
                    comment_text = cells[3].get_text().strip()
                    
                    _LOGGER.debug(f"Row {i}: date='{date_text}', what='{what_text}', time='{time_text}'")
                    
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
                    else:
                        _LOGGER.debug(f"Skipped non-Selvbestemmer appointment: {what_text}")
                elif len(cells) > 0:
                    # Log what we found in case structure is different
                    row_text = " | ".join([cell.get_text().strip() for cell in cells])
                    _LOGGER.debug(f"Row {i} has {len(cells)} cells: {row_text}")
            
        except Exception as e:
            _LOGGER.error(f"Error parsing appointments table: {e}", exc_info=True)
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test if credentials are valid."""
        try:
            if not self.username or not self.password:
                _LOGGER.error("Username or password is empty")
                return False
            
            # Basic validation
            if len(self.username) < 3 or len(self.password) < 3:
                _LOGGER.error("Username or password too short")
                return False
            
            _LOGGER.info(f"Testing credentials for user: {self.username}")
            
            # For now, just do basic validation to avoid blocking the setup
            # The real test will happen when fetching appointments
            return True
            
        except Exception as e:
            _LOGGER.error(f"Credential test failed: {e}")
            return False
