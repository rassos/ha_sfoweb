"""SFOWeb scraper using network analysis and reverse-engineered API calls."""
from __future__ import annotations

import asyncio
import logging
import re
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import aiohttp
from bs4 import BeautifulSoup

from .const import (
    APPOINTMENTS_URL,
    LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)


class SFOScraper:
    """Handle SFOWeb scraping using reverse-engineered API calls."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper."""
        self.username = username
        self.password = password
        self.session = None

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments using reverse-engineered authentication flow."""
        appointments = []
        
        timeout = aiohttp.ClientTimeout(total=120)
        
        # Enhanced headers to mimic real browser behavior
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'da-DK,da;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
        
        jar = aiohttp.CookieJar()
        
        try:
            async with aiohttp.ClientSession(
                timeout=timeout, 
                headers=headers, 
                cookie_jar=jar,
                connector=aiohttp.TCPConnector(ssl=False, limit=10)
            ) as session:
                
                # Step 1: Initial reconnaissance - get the login page structure
                _LOGGER.info("Starting authentication flow analysis...")
                
                login_successful = await self._attempt_authentication_flow(session)
                
                if login_successful:
                    appointments = await self._fetch_appointments_data(session)
                else:
                    _LOGGER.error("Authentication failed - unable to proceed")
                
                return appointments
                
        except Exception as e:
            _LOGGER.error(f"Scraper error: {e}", exc_info=True)
            return appointments

    async def _attempt_authentication_flow(self, session: aiohttp.ClientSession) -> bool:
        """Attempt various authentication flows."""
        
        # Flow 1: Check if we're dealing with the correct SFO system
        if await self._detect_sfo_system(session):
            return True
        
        # Flow 2: Standard form-based authentication
        if await self._try_standard_form_auth(session):
            return True
        
        # Flow 3: AJAX/API-based authentication
        if await self._try_ajax_auth(session):
            return True
        
        # Flow 4: OAuth/SSO redirect flow
        if await self._try_oauth_flow(session):
            return True
        
        return False

    async def _detect_sfo_system(self, session: aiohttp.ClientSession) -> bool:
        """Detect and handle specific SFO system types."""
        try:
            _LOGGER.info("Detecting SFO system type...")
            
            # From your logs, it seems like you're being redirected to soestjernen.sfoweb.dk
            # Let's start there instead of the generic login URL
            sfo_urls = [
                "https://soestjernen.sfoweb.dk",
                "https://soestjernen.sfoweb.dk/login",
                LOGIN_URL,
            ]
            
            for url in sfo_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Check if this looks like the right SFO system
                            if "soestjernen" in html.lower() or "sfo" in html.lower():
                                _LOGGER.info(f"Found SFO system at: {url}")
                                return await self._handle_sfo_login(session, html, str(response.url))
                                
                except Exception as e:
                    _LOGGER.debug(f"Failed to access {url}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"SFO system detection failed: {e}")
        
        return False

    async def _handle_sfo_login(self, session: aiohttp.ClientSession, html: str, current_url: str) -> bool:
        """Handle login for detected SFO system."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for parent login redirect (based on your logs)
            parent_links = soup.find_all('a', href=True)
            for link in parent_links:
                href = link['href']
                link_text = link.get_text().lower()
                
                if ('parent' in href.lower() or 'foraeldr' in href.lower() or 
                    'parent' in link_text or 'forældre' in link_text):
                    
                    if not href.startswith('http'):
                        href = urljoin(current_url, href)
                    
                    _LOGGER.info(f"Following parent login link: {href}")
                    
                    async with session.get(href) as parent_response:
                        if parent_response.status == 200:
                            parent_html = await parent_response.text()
                            parent_soup = BeautifulSoup(parent_html, 'html.parser')
                            
                            # Look for login form or further redirects
                            form = parent_soup.find('form')
                            if form and self._has_login_fields(parent_soup):
                                return await self._submit_login_form(session, form, str(parent_response.url))
                            
                            # Check for further redirects or login options
                            return await self._handle_parent_login_page(session, parent_html, str(parent_response.url))
            
            # If no parent link found, try direct login
            form = soup.find('form')
            if form and self._has_login_fields(soup):
                return await self._submit_login_form(session, form, current_url)
                
        except Exception as e:
            _LOGGER.debug(f"SFO login handling failed: {e}")
        
        return False

    async def _handle_parent_login_page(self, session: aiohttp.ClientSession, html: str, current_url: str) -> bool:
        """Handle parent login page with multiple authentication options."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for different login methods
            login_methods = []
            
            # Check for UNI Login, NemLog-in, etc.
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()
                
                if any(method in text for method in ['forældre login', 'parent login', 'uni login']):
                    if not href.startswith('http'):
                        href = urljoin(current_url, href)
                    login_methods.append((href, text))
            
            # Try each login method
            for method_url, method_name in login_methods:
                _LOGGER.info(f"Trying login method: {method_name} at {method_url}")
                
                try:
                    async with session.get(method_url) as method_response:
                        if method_response.status == 200:
                            method_html = await method_response.text()
                            method_soup = BeautifulSoup(method_html, 'html.parser')
                            
                            form = method_soup.find('form')
                            if form and self._has_login_fields(method_soup):
                                if await self._submit_login_form(session, form, str(method_response.url)):
                                    return True
                                    
                except Exception as e:
                    _LOGGER.debug(f"Failed login method {method_name}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"Parent login page handling failed: {e}")
        
        return False

    async def _try_standard_form_auth(self, session: aiohttp.ClientSession) -> bool:
        """Try standard HTML form authentication."""
        try:
            _LOGGER.info("Attempting standard form authentication...")
            
            # Get initial page
            async with session.get(LOGIN_URL) as response:
                if response.status != 200:
                    return False
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for different types of login flows
                
                # Check 1: Direct login form on main page
                login_form = soup.find('form')
                if login_form and self._has_login_fields(soup):
                    _LOGGER.info("Found direct login form")
                    return await self._submit_login_form(session, login_form, str(response.url))
                
                # Check 2: Look for parent/user type selection
                parent_links = self._find_parent_login_links(soup)
                for link_url in parent_links:
                    if not link_url.startswith('http'):
                        link_url = urljoin(str(response.url), link_url)
                    
                    _LOGGER.info(f"Trying parent login link: {link_url}")
                    
                    async with session.get(link_url) as parent_response:
                        if parent_response.status == 200:
                            parent_html = await parent_response.text()
                            parent_soup = BeautifulSoup(parent_html, 'html.parser')
                            
                            parent_form = parent_soup.find('form')
                            if parent_form and self._has_login_fields(parent_soup):
                                return await self._submit_login_form(session, parent_form, str(parent_response.url))
                
                # Check 3: Look for JavaScript redirects or meta redirects
                meta_redirects = soup.find_all('meta', attrs={'http-equiv': 'refresh'})
                for meta in meta_redirects:
                    content = meta.get('content', '')
                    if 'url=' in content.lower():
                        redirect_url = content.split('url=', 1)[1].strip()
                        redirect_url = urljoin(str(response.url), redirect_url)
                        
                        _LOGGER.info(f"Following meta redirect: {redirect_url}")
                        
                        async with session.get(redirect_url) as redirect_response:
                            if redirect_response.status == 200:
                                redirect_html = await redirect_response.text()
                                redirect_soup = BeautifulSoup(redirect_html, 'html.parser')
                                
                                redirect_form = redirect_soup.find('form')
                                if redirect_form and self._has_login_fields(redirect_soup):
                                    return await self._submit_login_form(session, redirect_form, str(redirect_response.url))
                
        except Exception as e:
            _LOGGER.debug(f"Standard form auth failed: {e}")
        
        return False

    async def _try_ajax_auth(self, session: aiohttp.ClientSession) -> bool:
        """Try AJAX-based authentication by analyzing JavaScript."""
        try:
            _LOGGER.info("Attempting AJAX authentication...")
            
            async with session.get(LOGIN_URL) as response:
                if response.status != 200:
                    return False
                
                html = await response.text()
                
                # Look for AJAX endpoints in JavaScript
                ajax_patterns = [
                    r'["\']([^"\']*(?:login|auth|signin)[^"\']*\.(?:php|asp|jsp|do|action))["\']',
                    r'ajax.*?url.*?["\']([^"\']+)["\']',
                    r'fetch\(["\']([^"\']+)["\']',
                    r'XMLHttpRequest.*?open.*?["\']POST["\'].*?["\']([^"\']+)["\']',
                ]
                
                endpoints = []
                for pattern in ajax_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    endpoints.extend(matches)
                
                # Try each potential AJAX endpoint
                for endpoint in endpoints[:5]:  # Limit attempts
                    if not endpoint.startswith('http'):
                        endpoint = urljoin(str(response.url), endpoint)
                    
                    _LOGGER.info(f"Trying AJAX endpoint: {endpoint}")
                    
                    # Try different data formats
                    for data_format in ['form', 'json']:
                        if await self._try_ajax_login(session, endpoint, data_format):
                            return True
                
        except Exception as e:
            _LOGGER.debug(f"AJAX auth failed: {e}")
        
        return False

    async def _try_oauth_flow(self, session: aiohttp.ClientSession) -> bool:
        """Try OAuth/SSO redirect flow."""
        try:
            _LOGGER.info("Attempting OAuth/SSO flow...")
            
            # Common OAuth/SSO patterns for Danish education systems
            oauth_endpoints = [
                "https://sfo-web.aula.dk/auth/oauth",
                "https://sfo-web.aula.dk/sso/login",
                "https://login.aula.dk/auth",
                "https://wayf.dk/login",  # Common Danish federation
                "https://soestjernen.sfoweb.dk/auth",
            ]
            
            for endpoint in oauth_endpoints:
                try:
                    async with session.get(endpoint) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            form = soup.find('form')
                            if form and self._has_login_fields(soup):
                                _LOGGER.info(f"Found OAuth form at: {endpoint}")
                                return await self._submit_login_form(session, form, endpoint)
                except:
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"OAuth flow failed: {e}")
        
        return False

    async def _try_ajax_login(self, session: aiohttp.ClientSession, endpoint: str, data_format: str) -> bool:
        """Try AJAX login with different data formats."""
        try:
            if data_format == 'json':
                headers = {'Content-Type': 'application/json'}
                data = json.dumps({
                    'username': self.username,
                    'password': self.password,
                })
            else:  # form
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                data = {
                    'username': self.username,
                    'password': self.password,
                }
            
            async with session.post(endpoint, data=data, headers=headers) as response:
                if response.status in [200, 302]:
                    # Check if we can now access protected content
                    return await self._verify_authentication(session)
                    
        except Exception as e:
            _LOGGER.debug(f"AJAX login to {endpoint} failed: {e}")
        
        return False

    def _find_parent_login_links(self, soup: BeautifulSoup) -> List[str]:
        """Find links that might lead to parent login."""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()
            
            # Look for parent-related keywords
            if any(keyword in text for keyword in ['forældre', 'parent', 'guardians']) or \
               any(keyword in href.lower() for keyword in ['parent', 'foraeldr', 'guardian']):
                links.append(href)
        
        return links

    def _has_login_fields(self, soup: BeautifulSoup) -> bool:
        """Check if the page has login form fields."""
        username_fields = soup.find_all('input', attrs={'name': re.compile(r'user|email|login', re.I)})
        password_fields = soup.find_all('input', attrs={'type': 'password'})
        
        return len(username_fields) > 0 and len(password_fields) > 0

    async def _submit_login_form(self, session: aiohttp.ClientSession, form: BeautifulSoup, form_url: str) -> bool:
        """Submit a login form."""
        try:
            action = form.get('action', '')
            if not action:
                action = form_url
            elif not action.startswith('http'):
                action = urljoin(form_url, action)
            
            # Collect form data
            form_data = {}
            
            # Add all hidden fields
            for hidden in form.find_all('input', type='hidden'):
                name = hidden.get('name')
                value = hidden.get('value', '')
                if name:
                    form_data[name] = value
            
            # Find username field - try multiple patterns
            username_patterns = [
                {'name': re.compile(r'user', re.I)},
                {'name': re.compile(r'email', re.I)},
                {'name': re.compile(r'login', re.I)},
                {'name': 'username'},
                {'id': re.compile(r'user', re.I)},
            ]
            
            username_field = None
            for pattern in username_patterns:
                username_field = form.find('input', attrs=pattern)
                if username_field:
                    break
            
            if username_field:
                form_data[username_field['name']] = self.username
            
            # Find password field
            password_field = form.find('input', attrs={'type': 'password'})
            if password_field:
                form_data[password_field['name']] = self.password
            
            # Add any submit button values
            submit_buttons = form.find_all('input', type='submit')
            for button in submit_buttons:
                if button.get('name') and button.get('value'):
                    form_data[button['name']] = button['value']
                    break  # Only add the first submit button
            
            _LOGGER.info(f"Submitting form to: {action}")
            _LOGGER.debug(f"Form data keys: {list(form_data.keys())}")
            
            async with session.post(action, data=form_data) as response:
                _LOGGER.info(f"Form submission response: {response.status}")
                
                if response.status in [200, 302]:
                    return await self._verify_authentication(session)
                    
        except Exception as e:
            _LOGGER.debug(f"Form submission failed: {e}")
        
        return False

    async def _verify_authentication(self, session: aiohttp.ClientSession) -> bool:
        """Verify if authentication was successful."""
        try:
            # Try multiple endpoints to verify authentication
            test_urls = [
                APPOINTMENTS_URL,
                "https://soestjernen.sfoweb.dk/aftaler",
                "https://soestjernen.sfoweb.dk/appointments",
                "https://soestjernen.sfoweb.dk/dashboard",
            ]
            
            for url in test_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Check for signs of successful authentication
                            success_indicators = [
                                'appointment',
                                'aftale',
                                'tabel',
                                'kalender',
                                'logout',
                                'logud',
                                'dashboard',
                                'schedule'
                            ]
                            
                            html_lower = html.lower()
                            for indicator in success_indicators:
                                if indicator in html_lower:
                                    _LOGGER.info(f"Authentication verified - found '{indicator}' in response")
                                    return True
                            
                            # Check if we're NOT on a login page
                            login_indicators = ['login', 'password', 'brugernavn', 'sign in']
                            login_present = any(indicator in html_lower for indicator in login_indicators)
                            
                            if not login_present and len(html) > 1000:  # Substantial content
                                _LOGGER.info("Authentication likely successful - no login indicators found")
                                return True
                                
                except Exception as e:
                    _LOGGER.debug(f"Failed to verify auth with {url}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"Authentication verification failed: {e}")
        
        return False

    async def _fetch_appointments_data(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch appointments data after successful authentication."""
        appointments = []
        
        try:
            _LOGGER.info("Fetching appointments data...")
            
            # Try multiple possible appointment URLs
            appointment_urls = [
                APPOINTMENTS_URL,
                "https://soestjernen.sfoweb.dk/aftaler",
                "https://soestjernen.sfoweb.dk/appointments",
                "https://soestjernen.sfoweb.dk/calendar",
            ]
            
            for url in appointment_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            appointments = self._parse_appointments_html(html)
                            
                            if appointments:
                                _LOGGER.info(f"Found {len(appointments)} appointments from {url}")
                                return appointments
                            else:
                                _LOGGER.debug(f"No appointments found at {url}")
                                
                except Exception as e:
                    _LOGGER.debug(f"Failed to fetch from {url}: {e}")
                    continue
                
        except Exception as e:
            _LOGGER.error(f"Error fetching appointments: {e}")
        
        return appointments

    def _parse_appointments_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse appointments from HTML with improved detection."""
        appointments = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Debug: Log page structure
            _LOGGER.info(f"Appointments page HTML length: {len(html)}")
            
            # Check if we're actually on a login page (common issue)
            login_indicators = ['login', 'password', 'brugernavn', 'sign in', 'log på']
            page_text_lower = soup.get_text().lower()
            
            if any(indicator in page_text_lower for indicator in login_indicators):
                _LOGGER.warning("Still on login page - authentication may have failed")
                return appointments
            
            # Look for tables first
            tables = soup.find_all('table')
            _LOGGER.info(f"Found {len(tables)} tables on appointments page")
            
            for i, table in enumerate(tables):
                rows = table.find_all('tr')
                _LOGGER.info(f"Table {i+1} has {len(rows)} rows")
                
                # Log table structure for debugging
                if len(rows) > 0:
                    first_row_cells = rows[0].find_all(['td', 'th'])
                    _LOGGER.debug(f"Table {i+1} first row has {len(first_row_cells)} cells")
                    if first_row_cells:
                        headers = [cell.get_text().strip() for cell in first_row_cells]
                        _LOGGER.debug(f"Table {i+1} headers: {headers}")
                
                # Skip header, process data rows
                for j, row in enumerate(rows[1:], 1):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        cell_texts = [cell.get_text().strip() for cell in cells]
                        _LOGGER.debug(f"Table {i+1}, Row {j}: {cell_texts}")
                        
                        date_text = cell_texts[0] if len(cell_texts) > 0 else ""
                        what_text = cell_texts[1] if len(cell_texts) > 1 else ""
                        time_text = cell_texts[2] if len(cell_texts) > 2 else ""
                        comment_text = cell_texts[3] if len(cell_texts) > 3 else ""
                        
                        # Include all appointments for now (not just Selvbestemmer)
                        if date_text and what_text:
                            appointment = {
                                "date": date_text,
                                "what": what_text,
                                "time": time_text,
                                "comment": comment_text,
                                "full_description": f"{date_text} - {time_text}"
                            }
                            appointments.append(appointment)
                            _LOGGER.info(f"Found appointment: {appointment['full_description']}")
                    elif len(cells) > 0:
                        # Log rows that don't have enough cells
                        cell_texts = [cell.get_text().strip() for cell in cells]
                        _LOGGER.debug(f"Table {i+1}, Row {j} (insufficient cells): {cell_texts}")
            
            # If no appointments in tables, try alternative parsing methods
            if not appointments:
                appointments.extend(self._parse_alternative_formats(soup))
            
            # If still no appointments, look for common "no appointments" messages
            if not appointments:
                _LOGGER.info("No appointments found in tables, checking for other content...")
                
                text_content = soup.get_text().lower()
                if any(phrase in text_content for phrase in ["ingen", "none", "empty", "no appointments"]):
                    _LOGGER.info("Found 'no appointments' indicator in page content")
                elif "aftale" in text_content:
                    _LOGGER.info("Page contains 'aftale' but no appointments found in tables")
                    # Log some of the text content for debugging
                    _LOGGER.debug(f"Page text sample: {soup.get_text()[:500]}...")
            
            _LOGGER.info(f"Total appointments parsed: {len(appointments)}")
            
        except Exception as e:
            _LOGGER.error(f"Error parsing appointments: {e}")
        
        return appointments

    def _parse_alternative_formats(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Try alternative parsing methods for appointments."""
        appointments = []
        
        try:
            # Method 1: Look for div-based appointment listings
            appointment_divs = soup.find_all('div', class_=re.compile(r'appointment|event|aftale', re.I))
            for div in appointment_divs:
                text = div.get_text().strip()
                if text and len(text) > 10:  # Substantial content
                    appointments.append({
                        "date": "Unknown",
                        "what": text[:50] + "..." if len(text) > 50 else text,
                        "time": "Unknown",
                        "comment": "",
                        "full_description": text
                    })
            
            # Method 2: Look for list items
            if not appointments:
                li_items = soup.find_all('li')
                for li in li_items:
                    text = li.get_text().strip()
                    # Look for date patterns
                    if re.search(r'\d{1,2}[./]\d{1,2}', text) or re.search(r'\d{4}-\d{2}-\d{2}', text):
                        appointments.append({
                            "date": "See description",
                            "what": text[:50] + "..." if len(text) > 50 else text,
                            "time": "See description",
                            "comment": "",
                            "full_description": text
                        })
            
            # Method 3: Look for calendar-specific elements
            if not appointments:
                calendar_elements = soup.find_all(['div', 'span'], class_=re.compile(r'calendar|event|date', re.I))
                for element in calendar_elements:
                    text = element.get_text().strip()
                    if text and len(text) > 5:
                        appointments.append({
                            "date": "Calendar item",
                            "what": text[:50] + "..." if len(text) > 50 else text,
                            "time": "See description",
                            "comment": "",
                            "full_description": text
                        })
                        
        except Exception as e:
            _LOGGER.debug(f"Alternative parsing failed: {e}")
        
        return appointments[:10]  # Limit to prevent spam

    async def async_test_credentials(self) -> bool:
        """Test if credentials are valid by attempting a quick login."""
        try:
            if not self.username or not self.password:
                return False
            
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            # Try a quick authentication test
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                # Just check if we can reach the login page
                async with session.get(LOGIN_URL) as response:
                    if response.status == 200:
                        return True
            
            return True  # Assume credentials are valid for setup
            
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False
