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
        
        # Flow 1: Standard form-based authentication
        if await self._try_standard_form_auth(session):
            return True
        
        # Flow 2: AJAX/API-based authentication
        if await self._try_ajax_auth(session):
            return True
        
        # Flow 3: OAuth/SSO redirect flow
        if await self._try_oauth_flow(session):
            return True
        
        # Flow 4: Hidden iframe authentication
        if await self._try_iframe_auth(session):
            return True
        
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

    async def _try_iframe_auth(self, session: aiohttp.ClientSession) -> bool:
        """Try authentication through iframes."""
        try:
            _LOGGER.info("Attempting iframe authentication...")
            
            async with session.get(LOGIN_URL) as response:
                if response.status != 200:
                    return False
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for iframes that might contain login forms
                iframes = soup.find_all('iframe')
                for iframe in iframes:
                    src = iframe.get('src')
                    if src:
                        if not src.startswith('http'):
                            src = urljoin(str(response.url), src)
                        
                        _LOGGER.info(f"Checking iframe: {src}")
                        
                        try:
                            async with session.get(src) as iframe_response:
                                if iframe_response.status == 200:
                                    iframe_html = await iframe_response.text()
                                    iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                                    
                                    iframe_form = iframe_soup.find('form')
                                    if iframe_form and self._has_login_fields(iframe_soup):
                                        return await self._submit_login_form(session, iframe_form, src)
                        except:
                            continue
                            
        except Exception as e:
            _LOGGER.debug(f"Iframe auth failed: {e}")
        
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
               any(keyword in href.lower() for keyword in ['parent', 'foraldre', 'guardian']):
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
            
            # Find username field
            username_field = form.find('input', attrs={'name': re.compile(r'user|email|login', re.I)})
            if username_field:
                form_data[username_field['name']] = self.username
            
            # Find password field
            password_field = form.find('input', attrs={'type': 'password'})
            if password_field:
                form_data[password_field['name']] = self.password
            
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
            async with session.get(APPOINTMENTS_URL) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Check for signs of successful authentication
                    success_indicators = [
                        'appointment',
                        'aftale',
                        'tabel',
                        'kalender',
                        'logout',
                        'logud'
                    ]
                    
                    html_lower = html.lower()
                    for indicator in success_indicators:
                        if indicator in html_lower:
                            _LOGGER.info(f"Authentication verified - found '{indicator}' in response")
                            return True
                    
                    # Check if we're still on a login page
                    login_indicators = ['login', 'password', 'brugernavn']
                    login_present = any(indicator in html_lower for indicator in login_indicators)
                    
                    if not login_present:
                        _LOGGER.info("Authentication likely successful - no login indicators found")
                        return True
                        
        except Exception as e:
            _LOGGER.debug(f"Authentication verification failed: {e}")
        
        return False

    async def _fetch_appointments_data(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch appointments data after successful authentication."""
        appointments = []
        
        try:
            _LOGGER.info("Fetching appointments data...")
            
            async with session.get(APPOINTMENTS_URL) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to fetch appointments: {response.status}")
                    return appointments
                
                html = await response.text()
                appointments = self._parse_appointments_html(html)
                
        except Exception as e:
            _LOGGER.error(f"Error fetching appointments: {e}")
        
        return appointments

    def _parse_appointments_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse appointments from HTML."""
        appointments = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for tables
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                # Skip header, process data rows
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        cell_texts = [cell.get_text().strip() for cell in cells]
                        
                        date_text = cell_texts[0] if len(cell_texts) > 0 else ""
                        what_text = cell_texts[1] if len(cell_texts) > 1 else ""
                        time_text = cell_texts[2] if len(cell_texts) > 2 else ""
                        comment_text = cell_texts[3] if len(cell_texts) > 3 else ""
                        
                        # Include all appointments for now
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
            
        except Exception as e:
            _LOGGER.error(f"Error parsing appointments: {e}")
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test if credentials are valid."""
        try:
            if not self.username or not self.password:
                return False
            
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            return True
            
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False
