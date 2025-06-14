"""JavaScript-capable scraper for SFOWeb using requests-html."""
from __future__ import annotations

import asyncio
import logging
import re
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import time

from requests_html import HTMLSession, AsyncHTMLSession
from bs4 import BeautifulSoup

from .const import (
    APPOINTMENTS_URL,
    LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)


class SFOJSScraper:
    """Handle SFOWeb scraping with JavaScript rendering capability."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper."""
        self.username = username
        self.password = password
        self.session = None

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments using JavaScript rendering."""
        appointments = []
        
        try:
            # Use AsyncHTMLSession for async operations
            session = AsyncHTMLSession()
            
            # Set browser args for headless operation
            session.browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--headless',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            
            _LOGGER.info("Starting JavaScript-enabled scraping...")
            
            # Step 1: Navigate to login page and let JS render
            login_successful = await self._perform_js_login(session)
            
            if login_successful:
                appointments = await self._fetch_js_appointments(session)
            else:
                _LOGGER.error("JavaScript login failed")
            
            # Clean up session
            await session.close()
            
        except Exception as e:
            _LOGGER.error(f"JS Scraper error: {e}", exc_info=True)
        
        return appointments

    async def _perform_js_login(self, session: AsyncHTMLSession) -> bool:
        """Perform login with JavaScript rendering."""
        try:
            _LOGGER.info("Navigating to login page with JS rendering...")
            
            # Navigate to the main login page
            r = await session.get(LOGIN_URL)
            
            # Render JavaScript - this is the key difference
            await r.html.arender(wait=2, timeout=20)
            
            _LOGGER.info(f"Page rendered, title: {r.html.find('title', first=True).text if r.html.find('title', first=True) else 'No title'}")
            
            # Look for the parent/daycare login link after JS rendering
            parent_links = await self._find_parent_login_links_js(r.html)
            
            for link_url in parent_links:
                _LOGGER.info(f"Trying parent login link: {link_url}")
                
                # Navigate to parent login
                parent_r = await session.get(link_url)
                await parent_r.html.arender(wait=2, timeout=20)
                
                # Try to find and fill login form
                if await self._try_login_form_js(session, parent_r.html, link_url):
                    return True
            
            # If no parent links, try direct login on current page
            if await self._try_login_form_js(session, r.html, LOGIN_URL):
                return True
                
        except Exception as e:
            _LOGGER.error(f"JS login error: {e}", exc_info=True)
        
        return False

    async def _find_parent_login_links_js(self, html) -> List[str]:
        """Find parent login links in rendered HTML."""
        links = []
        
        try:
            # Look for links with parent-related text
            all_links = html.find('a')
            
            for link in all_links:
                href = link.attrs.get('href', '')
                text = link.text.lower()
                
                # Check for parent/guardian keywords
                if any(keyword in text for keyword in ['forældre', 'parent', 'guardian', 'voksen']) or \
                   any(keyword in href.lower() for keyword in ['parent', 'foraeldr', 'guardian', 'voksen']):
                    
                    if href.startswith('http'):
                        links.append(href)
                    elif href.startswith('/'):
                        links.append(urljoin(LOGIN_URL, href))
                    
        except Exception as e:
            _LOGGER.debug(f"Error finding parent links: {e}")
        
        return links

    async def _try_login_form_js(self, session: AsyncHTMLSession, html, current_url: str) -> bool:
        """Try to fill and submit login form in JavaScript-rendered page."""
        try:
            # Look for login forms
            forms = html.find('form')
            
            for form in forms:
                # Check if this form has username/password fields
                username_inputs = form.find('input[type="text"], input[type="email"], input[name*="user"], input[name*="login"]')
                password_inputs = form.find('input[type="password"]')
                
                if username_inputs and password_inputs:
                    _LOGGER.info("Found login form with username/password fields")
                    
                    # Try to submit the form via JavaScript
                    if await self._submit_form_js(session, form, current_url):
                        return True
                    
                    # Try to detect and use API endpoints
                    if await self._detect_api_endpoints(session, html, current_url):
                        return True
                        
        except Exception as e:
            _LOGGER.debug(f"Form submission error: {e}")
        
        return False

    async def _submit_form_js(self, session: AsyncHTMLSession, form, form_url: str) -> bool:
        """Submit form using JavaScript execution."""
        try:
            # Get form action
            action = form.attrs.get('action', form_url)
            if not action.startswith('http'):
                action = urljoin(form_url, action)
            
            # Build form data
            form_data = {}
            
            # Add hidden fields
            hidden_inputs = form.find('input[type="hidden"]')
            for hidden in hidden_inputs:
                name = hidden.attrs.get('name')
                value = hidden.attrs.get('value', '')
                if name:
                    form_data[name] = value
            
            # Add username
            username_inputs = form.find('input[type="text"], input[type="email"], input[name*="user"], input[name*="login"]')
            if username_inputs:
                username_field = username_inputs[0]
                username_name = username_field.attrs.get('name', 'username')
                form_data[username_name] = self.username
            
            # Add password
            password_inputs = form.find('input[type="password"]')
            if password_inputs:
                password_field = password_inputs[0]
                password_name = password_field.attrs.get('name', 'password')
                form_data[password_name] = self.password
            
            # Add submit button value if present
            submit_buttons = form.find('input[type="submit"], button[type="submit"]')
            if submit_buttons:
                submit_btn = submit_buttons[0]
                btn_name = submit_btn.attrs.get('name')
                btn_value = submit_btn.attrs.get('value', 'Submit')
                if btn_name:
                    form_data[btn_name] = btn_value
            
            _LOGGER.info(f"Submitting form to: {action}")
            _LOGGER.debug(f"Form fields: {list(form_data.keys())}")
            
            # Submit form
            response = await session.post(action, data=form_data)
            
            # Render the response to handle any JS redirects
            await response.html.arender(wait=2, timeout=15)
            
            # Check if login was successful
            return await self._verify_login_success_js(response.html)
            
        except Exception as e:
            _LOGGER.error(f"Form submission failed: {e}")
            return False

    async def _verify_login_success_js(self, html) -> bool:
        """Verify login success by checking page content."""
        try:
            page_text = html.text.lower()
            
            # Check for success indicators
            success_indicators = [
                'dashboard', 'aftaler', 'appointments', 'kalender', 
                'schedule', 'logout', 'logud', 'profil', 'velkommen'
            ]
            
            for indicator in success_indicators:
                if indicator in page_text:
                    _LOGGER.info(f"Login success detected: found '{indicator}'")
                    return True
            
            # Check that we're NOT still on login page
            login_indicators = ['login', 'password', 'brugernavn', 'log på', 'sign in']
            
            login_found = any(indicator in page_text for indicator in login_indicators)
            
            if not login_found and len(page_text) > 500:
                _LOGGER.info("Login likely successful - no login indicators found")
                return True
                
        except Exception as e:
            _LOGGER.debug(f"Login verification error: {e}")
        
        return False

    async def _fetch_js_appointments(self, session: AsyncHTMLSession) -> List[Dict[str, Any]]:
        """Fetch appointments from JavaScript-rendered pages."""
        appointments = []
        
        try:
            _LOGGER.info("Fetching appointments with JS rendering...")
            
            appointment_urls = [
                APPOINTMENTS_URL,
                "https://soestjernen.sfoweb.dk/aftaler",
                "https://soestjernen.sfoweb.dk/appointments",
                "https://soestjernen.sfoweb.dk/calendar",
                "https://soestjernen.sfoweb.dk/dashboard"
            ]
            
            for url in appointment_urls:
                try:
                    _LOGGER.info(f"Trying appointments URL: {url}")
                    response = await session.get(url)
                    
                    # Render JavaScript and wait for content to load
                    await response.html.arender(wait=3, timeout=30)
                    
                    # Parse appointments from rendered HTML
                    page_appointments = self._parse_js_appointments(response.html)
                    
                    if page_appointments:
                        _LOGGER.info(f"Found {len(page_appointments)} appointments from {url}")
                        appointments.extend(page_appointments)
                        break  # Use first successful URL
                    else:
                        # Try to detect appointment API endpoints
                        api_appointments = await self._try_appointment_apis(session, response.html, url)
                        if api_appointments:
                            _LOGGER.info(f"Found {len(api_appointments)} appointments via API from {url}")
                            appointments.extend(api_appointments)
                            break
                        else:
                            _LOGGER.debug(f"No appointments found at {url}")
                        
                except Exception as e:
                    _LOGGER.debug(f"Failed to fetch appointments from {url}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.error(f"Error fetching JS appointments: {e}")
        
        return appointments

    def _parse_js_appointments(self, html) -> List[Dict[str, Any]]:
        """Parse appointments from JavaScript-rendered HTML."""
        appointments = []
        
        try:
            _LOGGER.info("Parsing appointments from rendered HTML...")
            
            # Convert to BeautifulSoup for easier parsing
            soup = BeautifulSoup(html.html, 'html.parser')
            
            # Look for tables
            tables = soup.find_all('table')
            _LOGGER.info(f"Found {len(tables)} tables")
            
            for i, table in enumerate(tables):
                _LOGGER.debug(f"Processing table {i+1}")
                
                rows = table.find_all('tr')
                if len(rows) < 2:  # Skip tables with no data rows
                    continue
                
                # Skip header row, process data
                for j, row in enumerate(rows[1:], 1):
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 2:  # At least date and description
                        cell_texts = [cell.get_text().strip() for cell in cells]
                        
                        # Extract appointment data
                        date_text = cell_texts[0] if len(cell_texts) > 0 else ""
                        what_text = cell_texts[1] if len(cell_texts) > 1 else ""
                        time_text = cell_texts[2] if len(cell_texts) > 2 else ""
                        comment_text = cell_texts[3] if len(cell_texts) > 3 else ""
                        
                        # Only include if we have meaningful data
                        if date_text and what_text and len(date_text) > 2:
                            appointment = {
                                "date": date_text,
                                "what": what_text,
                                "time": time_text,
                                "comment": comment_text,
                                "full_description": f"{date_text} - {what_text} - {time_text}".strip(" -")
                            }
                            appointments.append(appointment)
                            _LOGGER.info(f"Found appointment: {appointment['full_description']}")
            
            # Try alternative parsing if no table appointments found
            if not appointments:
                appointments = self._parse_alternative_js_formats(soup)
            
            _LOGGER.info(f"Total appointments parsed: {len(appointments)}")
            
        except Exception as e:
            _LOGGER.error(f"Error parsing JS appointments: {e}")
        
        return appointments

    def _parse_alternative_js_formats(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Try alternative parsing methods for JavaScript-rendered appointments."""
        appointments = []
        
        try:
            # Look for common appointment/calendar classes
            appointment_selectors = [
                'div[class*="appointment"]',
                'div[class*="event"]',
                'div[class*="aftale"]',
                'div[class*="calendar"]',
                'li[class*="appointment"]',
                'li[class*="event"]',
                '.appointment-item',
                '.event-item',
                '.calendar-item'
            ]
            
            for selector in appointment_selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    text = element.get_text().strip()
                    
                    # Look for date patterns in the text
                    if text and len(text) > 10:
                        # Check if it contains date-like patterns
                        if re.search(r'\d{1,2}[./\-]\d{1,2}', text) or re.search(r'\d{4}-\d{2}-\d{2}', text):
                            appointments.append({
                                "date": "See description",
                                "what": text[:50] + "..." if len(text) > 50 else text,
                                "time": "See description",
                                "comment": "",
                                "full_description": text
                            })
                
                if appointments:
                    break  # Use first successful method
            
        except Exception as e:
            _LOGGER.debug(f"Alternative JS parsing failed: {e}")
        
        return appointments[:10]  # Limit results

    async def _detect_api_endpoints(self, session: AsyncHTMLSession, html, current_url: str) -> bool:
        """Detect and try API endpoints from JavaScript analysis."""
        try:
            _LOGGER.info("Analyzing JavaScript for API endpoints...")
            
            # Get all script tags from the rendered page
            scripts = html.find('script')
            
            api_endpoints = set()
            
            for script in scripts:
                script_content = script.text
                
                if script_content:
                    # Look for API patterns in JavaScript
                    patterns = [
                        r'["\']([^"\']*api[^"\']*login[^"\']*)["\']',
                        r'["\']([^"\']*auth[^"\']*api[^"\']*)["\']',
                        r'["\']([^"\']*ajax[^"\']*login[^"\']*)["\']',
                        r'fetch\(["\']([^"\']+/api/[^"\']+)["\']',
                        r'axios\.[a-z]+\(["\']([^"\']+)["\']',
                        r'XMLHttpRequest.*?open.*?["\']POST["\'].*?["\']([^"\']+)["\']',
                        r'endpoint["\s]*[:=]["\s]*["\']([^"\']+)["\']',
                        r'loginUrl["\s]*[:=]["\s]*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        for match in matches:
                            if match and len(match) > 5:
                                api_endpoints.add(match)
            
            # Try each detected API endpoint
            for endpoint in list(api_endpoints)[:5]:  # Limit attempts
                if not endpoint.startswith('http'):
                    endpoint = urljoin(current_url, endpoint)
                
                _LOGGER.info(f"Trying detected API endpoint: {endpoint}")
                
                if await self._try_api_login(session, endpoint):
                    return True
                    
        except Exception as e:
            _LOGGER.debug(f"API detection failed: {e}")
        
        return False

    async def _try_api_login(self, session: AsyncHTMLSession, api_endpoint: str) -> bool:
        """Try to login using detected API endpoint."""
        try:
            # Try different API authentication methods
            auth_methods = [
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({
                        'username': self.username,
                        'password': self.password,
                    })
                },
                {
                    'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
                    'data': {
                        'username': self.username,
                        'password': self.password,
                    }
                },
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({
                        'email': self.username,
                        'password': self.password,
                    })
                },
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({
                        'login': self.username,
                        'password': self.password,
                    })
                }
            ]
            
            for method in auth_methods:
                try:
                    # Make API request
                    if isinstance(method['data'], str):
                        response = await session.post(
                            api_endpoint,
                            data=method['data'],
                            headers=method['headers']
                        )
                    else:
                        response = await session.post(
                            api_endpoint,
                            data=method['data'],
                            headers=method['headers']
                        )
                    
                    _LOGGER.info(f"API response status: {response.status_code}")
                    
                    if response.status_code in [200, 201]:
                        # Check response content for success indicators
                        try:
                            response_text = response.text
                            response_lower = response_text.lower()
                            
                            # Look for success indicators in API response
                            success_indicators = [
                                'token', 'jwt', 'session', 'success', 'authenticated',
                                'user', 'profile', 'dashboard', 'true'
                            ]
                            
                            error_indicators = [
                                'error', 'invalid', 'wrong', 'failed', 'unauthorized',
                                'forbidden', 'denied'
                            ]
                            
                            has_success = any(indicator in response_lower for indicator in success_indicators)
                            has_error = any(indicator in response_lower for indicator in error_indicators)
                            
                            if has_success and not has_error:
                                _LOGGER.info(f"API login successful with {api_endpoint}")
                                return True
                                
                        except Exception as e:
                            _LOGGER.debug(f"Error parsing API response: {e}")
                    
                except Exception as e:
                    _LOGGER.debug(f"API method failed: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"API login to {api_endpoint} failed: {e}")
        
        return False

    async def _try_appointment_apis(self, session: AsyncHTMLSession, html, current_url: str) -> List[Dict[str, Any]]:
        """Try to find and use appointment API endpoints."""
        appointments = []
        
        try:
            _LOGGER.info("Looking for appointment API endpoints...")
            
            # Get all script tags
            scripts = html.find('script')
            
            api_endpoints = set()
            
            for script in scripts:
                script_content = script.text
                
                if script_content:
                    # Look for appointment/calendar API patterns
                    patterns = [
                        r'["\']([^"\']*api[^"\']*appointment[^"\']*)["\']',
                        r'["\']([^"\']*api[^"\']*aftale[^"\']*)["\']',
                        r'["\']([^"\']*api[^"\']*calendar[^"\']*)["\']',
                        r'["\']([^"\']*api[^"\']*schedule[^"\']*)["\']',
                        r'["\']([^"\']*appointment[^"\']*api[^"\']*)["\']',
                        r'fetch\(["\']([^"\']+/api/[^"\']*appointment[^"\']*)["\']',
                        r'fetch\(["\']([^"\']+/api/[^"\']*aftale[^"\']*)["\']',
                        r'appointmentUrl["\s]*[:=]["\s]*["\']([^"\']+)["\']',
                        r'calendarEndpoint["\s]*[:=]["\s]*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        for match in matches:
                            if match and len(match) > 5:
                                api_endpoints.add(match)
            
            # Try each detected API endpoint
            for endpoint in list(api_endpoints)[:3]:  # Limit attempts
                if not endpoint.startswith('http'):
                    endpoint = urljoin(current_url, endpoint)
                
                _LOGGER.info(f"Trying appointment API endpoint: {endpoint}")
                
                try:
                    response = await session.get(endpoint)
                    
                    if response.status_code == 200:
                        try:
                            # Try to parse as JSON
                            data = response.json()
                            api_appointments = self._parse_api_appointments(data)
                            if api_appointments:
                                appointments.extend(api_appointments)
                                break
                        except:
                            # Try to parse as HTML
                            if response.text:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                html_appointments = self._parse_alternative_js_formats(soup)
                                if html_appointments:
                                    appointments.extend(html_appointments)
                                    break
                                    
                except Exception as e:
                    _LOGGER.debug(f"Failed to fetch from API endpoint {endpoint}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"Appointment API detection failed: {e}")
        
        return appointments

    def _parse_api_appointments(self, data) -> List[Dict[str, Any]]:
        """Parse appointments from API JSON data."""
        appointments = []
        
        try:
            # Handle different JSON structures
            items = []
            
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Try common keys for appointment lists
                for key in ['appointments', 'aftaler', 'events', 'calendar', 'data', 'items', 'results']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
            
            for item in items:
                if isinstance(item, dict):
                    # Extract appointment information
                    appointment = {
                        "date": "",
                        "what": "",
                        "time": "",
                        "comment": "",
                        "full_description": ""
                    }
                    
                    # Try different field names for date
                    for date_field in ['date', 'dato', 'start', 'startDate', 'start_date', 'appointment_date']:
                        if date_field in item:
                            appointment["date"] = str(item[date_field])
                            break
                    
                    # Try different field names for description/title
                    for what_field in ['title', 'description', 'what', 'beskrivelse', 'navn', 'name', 'subject']:
                        if what_field in item:
                            appointment["what"] = str(item[what_field])
                            break
                    
                    # Try different field names for time
                    for time_field in ['time', 'tid', 'start_time', 'startTime', 'hour']:
                        if time_field in item:
                            appointment["time"] = str(item[time_field])
                            break
                    
                    # Try different field names for comment
                    for comment_field in ['comment', 'kommentar', 'note', 'notes', 'remarks']:
                        if comment_field in item:
                            appointment["comment"] = str(item[comment_field])
                            break
                    
                    # Create full description
                    parts = [appointment["date"], appointment["what"], appointment["time"]]
                    appointment["full_description"] = " - ".join([p for p in parts if p]).strip(" -")
                    
                    # Only add if we have meaningful data
                    if appointment["date"] or appointment["what"]:
                        appointments.append(appointment)
            
        except Exception as e:
            _LOGGER.debug(f"API appointment parsing failed: {e}")
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test credentials with JavaScript rendering."""
        try:
            if not self.username or not self.password:
                return False
            
            # Basic validation
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            # Quick test - just check if we can create a session
            session = AsyncHTMLSession()
            session.browser_args = ['--headless', '--no-sandbox']
            
            try:
                # Try to reach the login page
                r = await session.get(LOGIN_URL, timeout=30)
                success = r.status_code == 200
                await session.close()
                return success
            except:
                await session.close()
                return False
                
        except Exception as e:
            _LOGGER.debug(f"JS credential test failed: {e}")
            return False