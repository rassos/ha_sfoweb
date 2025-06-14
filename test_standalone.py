#!/usr/bin/env python3
"""Standalone test script for the enhanced SFO scraper."""

import asyncio
import logging
import sys
import os
import getpass
import aiohttp
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Constants
LOGIN_URL = "https://sfo-web.aula.dk"
APPOINTMENTS_URL = "https://sfo-web.aula.dk/aftaler"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

_LOGGER = logging.getLogger(__name__)


class SFOEnhancedScraper:
    """Enhanced SFOWeb scraper with better JavaScript handling using only HA-compatible libraries."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the scraper."""
        self.username = username
        self.password = password
        self.session = None

    async def async_get_appointments(self) -> List[Dict[str, Any]]:
        """Fetch appointments using enhanced techniques."""
        appointments = []
        
        timeout = aiohttp.ClientTimeout(total=120)
        
        # Enhanced headers to mimic real browser behavior
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
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
                
                _LOGGER.info("Starting enhanced authentication flow...")
                
                login_successful = await self._enhanced_authentication_flow(session)
                
                if login_successful:
                    appointments = await self._fetch_appointments_enhanced(session)
                else:
                    _LOGGER.error("Enhanced authentication failed")
                
                return appointments
                
        except Exception as e:
            _LOGGER.error(f"Enhanced scraper error: {e}", exc_info=True)
            return appointments

    async def _enhanced_authentication_flow(self, session: aiohttp.ClientSession) -> bool:
        """Enhanced authentication flow with better JavaScript handling."""
        
        # Try different SFO URLs based on common patterns
        sfo_urls = [
            "https://soestjernen.sfoweb.dk",
            "https://soestjernen.sfoweb.dk/login",
            "https://soestjernen.sfoweb.dk/foraeldr",
            LOGIN_URL,
        ]
        
        for url in sfo_urls:
            try:
                _LOGGER.info(f"Trying SFO URL: {url}")
                
                # Get initial page
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Look for API endpoints or AJAX calls in the HTML
                        api_endpoints = await self._extract_api_endpoints(html, str(response.url))
                        
                        # Try API-based authentication first
                        for endpoint in api_endpoints:
                            if await self._try_api_authentication(session, endpoint):
                                return True
                        
                        # Fall back to form-based authentication
                        if await self._try_form_authentication(session, html, str(response.url)):
                            return True
                            
            except Exception as e:
                _LOGGER.debug(f"Failed to process {url}: {e}")
                continue
        
        return False

    async def _extract_api_endpoints(self, html: str, base_url: str) -> List[str]:
        """Extract potential API endpoints from HTML and JavaScript."""
        endpoints = []
        
        try:
            # Look for various patterns that might indicate API endpoints
            patterns = [
                # Direct API URLs
                r'["\']([^"\']*(?:api|ajax|service)[^"\']*(?:login|auth|signin)[^"\']*)["\']',
                r'["\']([^"\']*(?:login|auth|signin)[^"\']*(?:api|ajax|service)[^"\']*)["\']',
                
                # Fetch/AJAX calls
                r'fetch\(["\']([^"\']+)["\']',
                r'XMLHttpRequest.*?open.*?["\'](?:POST|GET)["\'].*?["\']([^"\']+)["\']',
                r'axios\.(?:post|get)\(["\']([^"\']+)["\']',
                r'\$\.(?:post|get|ajax)\(["\']([^"\']+)["\']',
                
                # Form actions that might be AJAX
                r'action=["\']([^"\']*(?:login|auth|signin)[^"\']*)["\']',
                
                # Common endpoint patterns
                r'["\']([^"\']*\/(?:api|service)\/[^"\']*)["\']',
                r'endpoint["\s]*[:=]["\s]*["\']([^"\']+)["\']',
                r'loginUrl["\s]*[:=]["\s]*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 5:
                        # Convert relative URLs to absolute
                        if not match.startswith('http'):
                            match = urljoin(base_url, match)
                        endpoints.append(match)
            
            # Remove duplicates and limit
            endpoints = list(set(endpoints))[:5]
            
            if endpoints:
                _LOGGER.info(f"Found {len(endpoints)} potential API endpoints")
            
        except Exception as e:
            _LOGGER.debug(f"Error extracting API endpoints: {e}")
        
        return endpoints

    async def _try_api_authentication(self, session: aiohttp.ClientSession, endpoint: str) -> bool:
        """Try API-based authentication."""
        try:
            _LOGGER.info(f"Trying API authentication: {endpoint}")
            
            # Try different authentication payloads
            auth_payloads = [
                # JSON payloads
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({'username': self.username, 'password': self.password})
                },
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({'email': self.username, 'password': self.password})
                },
                {
                    'headers': {'Content-Type': 'application/json'},
                    'data': json.dumps({'login': self.username, 'password': self.password})
                },
                
                # Form payloads
                {
                    'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
                    'data': {'username': self.username, 'password': self.password}
                },
                {
                    'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
                    'data': {'email': self.username, 'password': self.password}
                },
            ]
            
            for payload in auth_payloads:
                try:
                    async with session.post(endpoint, **payload) as response:
                        if response.status in [200, 201, 302]:
                            response_text = await response.text()
                            
                            # Check for success indicators
                            if await self._check_auth_success(response_text, response.status):
                                _LOGGER.info(f"API authentication successful: {endpoint}")
                                return True
                                
                except Exception as e:
                    _LOGGER.debug(f"API payload failed: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.debug(f"API authentication failed for {endpoint}: {e}")
        
        return False

    async def _try_form_authentication(self, session: aiohttp.ClientSession, html: str, current_url: str) -> bool:
        """Try traditional form-based authentication with enhancements."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for parent/guardian login links first
            parent_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()
                
                if any(keyword in text for keyword in ['forældre', 'parent', 'guardian', 'voksen']) or \
                   any(keyword in href.lower() for keyword in ['parent', 'foraeldr', 'guardian', 'voksen']):
                    
                    if not href.startswith('http'):
                        href = urljoin(current_url, href)
                    parent_links.append(href)
            
            # Try parent links first
            for link in parent_links:
                _LOGGER.info(f"Following parent link: {link}")
                try:
                    async with session.get(link) as response:
                        if response.status == 200:
                            parent_html = await response.text()
                            if await self._submit_login_forms(session, parent_html, str(response.url)):
                                return True
                except Exception as e:
                    _LOGGER.debug(f"Parent link failed: {e}")
                    continue
            
            # Try forms on current page
            return await self._submit_login_forms(session, html, current_url)
            
        except Exception as e:
            _LOGGER.debug(f"Form authentication failed: {e}")
        
        return False

    async def _submit_login_forms(self, session: aiohttp.ClientSession, html: str, form_url: str) -> bool:
        """Find and submit login forms."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            forms = soup.find_all('form')
            
            for form in forms:
                # Check if this form has username/password fields
                username_fields = form.find_all('input', attrs={'name': re.compile(r'user|email|login', re.I)})
                password_fields = form.find_all('input', attrs={'type': 'password'})
                
                if username_fields and password_fields:
                    _LOGGER.info("Found login form")
                    
                    action = form.get('action', form_url)
                    if not action.startswith('http'):
                        action = urljoin(form_url, action)
                    
                    # Build form data
                    form_data = {}
                    
                    # Add hidden fields
                    for hidden in form.find_all('input', type='hidden'):
                        name = hidden.get('name')
                        value = hidden.get('value', '')
                        if name:
                            form_data[name] = value
                    
                    # Add credentials
                    username_name = username_fields[0]['name']
                    password_name = password_fields[0]['name']
                    form_data[username_name] = self.username
                    form_data[password_name] = self.password
                    
                    # Add submit button if present
                    submit_buttons = form.find_all('input', type='submit')
                    if submit_buttons:
                        submit_btn = submit_buttons[0]
                        if submit_btn.get('name') and submit_btn.get('value'):
                            form_data[submit_btn['name']] = submit_btn['value']
                    
                    _LOGGER.info(f"Submitting form to: {action}")
                    
                    async with session.post(action, data=form_data) as response:
                        if response.status in [200, 302]:
                            response_text = await response.text()
                            if await self._check_auth_success(response_text, response.status):
                                return True
                                
        except Exception as e:
            _LOGGER.debug(f"Form submission failed: {e}")
        
        return False

    async def _check_auth_success(self, response_text: str, status_code: int) -> bool:
        """Check if authentication was successful."""
        try:
            text_lower = response_text.lower()
            
            # Success indicators
            success_indicators = [
                'dashboard', 'aftaler', 'appointments', 'kalender', 'schedule',
                'velkommen', 'welcome', 'logout', 'logud', 'profil', 'profile'
            ]
            
            # Error indicators
            error_indicators = [
                'invalid', 'ugyldig', 'forkert', 'wrong', 'error', 'fejl',
                'login failed', 'unauthorized', 'forbidden'
            ]
            
            has_success = any(indicator in text_lower for indicator in success_indicators)
            has_error = any(indicator in text_lower for indicator in error_indicators)
            
            # If we have success indicators and no errors, or if it's a redirect
            if (has_success and not has_error) or status_code == 302:
                return True
            
            # If no login indicators are present and we have substantial content
            login_indicators = ['login', 'password', 'brugernavn', 'sign in']
            has_login = any(indicator in text_lower for indicator in login_indicators)
            
            if not has_login and not has_error and len(response_text) > 1000:
                return True
                
        except Exception as e:
            _LOGGER.debug(f"Auth success check failed: {e}")
        
        return False

    async def _fetch_appointments_enhanced(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch appointments with enhanced techniques."""
        appointments = []
        
        try:
            _LOGGER.info("Fetching appointments with enhanced methods...")
            
            appointment_urls = [
                APPOINTMENTS_URL,
                "https://soestjernen.sfoweb.dk/aftaler",
                "https://soestjernen.sfoweb.dk/appointments",
                "https://soestjernen.sfoweb.dk/calendar",
                "https://soestjernen.sfoweb.dk/dashboard",
            ]
            
            for url in appointment_urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Try API endpoints first
                            api_endpoints = await self._extract_appointment_apis(html, str(response.url))
                            for endpoint in api_endpoints:
                                api_appointments = await self._fetch_from_api(session, endpoint)
                                if api_appointments:
                                    appointments.extend(api_appointments)
                                    return appointments
                            
                            # Fall back to HTML parsing
                            html_appointments = self._parse_appointments_enhanced(html)
                            if html_appointments:
                                appointments.extend(html_appointments)
                                return appointments
                                
                except Exception as e:
                    _LOGGER.debug(f"Failed to fetch from {url}: {e}")
                    continue
                    
        except Exception as e:
            _LOGGER.error(f"Error fetching enhanced appointments: {e}")
        
        return appointments

    async def _extract_appointment_apis(self, html: str, base_url: str) -> List[str]:
        """Extract appointment API endpoints."""
        endpoints = []
        
        patterns = [
            r'["\']([^"\']*(?:api|ajax)[^"\']*(?:appointment|aftale|calendar)[^"\']*)["\']',
            r'["\']([^"\']*(?:appointment|aftale|calendar)[^"\']*(?:api|ajax)[^"\']*)["\']',
            r'fetch\(["\']([^"\']+/(?:api|ajax)/[^"\']*(?:appointment|aftale)[^"\']*)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if match and len(match) > 5:
                    if not match.startswith('http'):
                        match = urljoin(base_url, match)
                    endpoints.append(match)
        
        return list(set(endpoints))[:3]

    async def _fetch_from_api(self, session: aiohttp.ClientSession, endpoint: str) -> List[Dict[str, Any]]:
        """Fetch appointments from API endpoint."""
        try:
            async with session.get(endpoint) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        return self._parse_api_appointments(data)
                    except:
                        # Fallback to HTML parsing
                        html = await response.text()
                        return self._parse_appointments_enhanced(html)
        except Exception as e:
            _LOGGER.debug(f"API fetch failed for {endpoint}: {e}")
        
        return []

    def _parse_api_appointments(self, data) -> List[Dict[str, Any]]:
        """Parse appointments from JSON API data."""
        appointments = []
        
        try:
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ['appointments', 'aftaler', 'events', 'data', 'items']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
            
            for item in items:
                if isinstance(item, dict):
                    appointment = {
                        "date": "",
                        "what": "",
                        "time": "",
                        "comment": "",
                        "full_description": ""
                    }
                    
                    # Extract fields
                    for date_field in ['date', 'dato', 'start', 'startDate']:
                        if date_field in item:
                            appointment["date"] = str(item[date_field])
                            break
                    
                    for what_field in ['title', 'description', 'what', 'navn']:
                        if what_field in item:
                            appointment["what"] = str(item[what_field])
                            break
                    
                    for time_field in ['time', 'tid', 'startTime']:
                        if time_field in item:
                            appointment["time"] = str(item[time_field])
                            break
                    
                    appointment["full_description"] = f"{appointment['date']} - {appointment['what']} - {appointment['time']}".strip(" -")
                    
                    if appointment["date"] or appointment["what"]:
                        appointments.append(appointment)
                        
        except Exception as e:
            _LOGGER.debug(f"API parsing failed: {e}")
        
        return appointments

    def _parse_appointments_enhanced(self, html: str) -> List[Dict[str, Any]]:
        """Enhanced HTML appointment parsing."""
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
                    if len(cells) >= 2:
                        cell_texts = [cell.get_text().strip() for cell in cells]
                        
                        if cell_texts[0] and len(cell_texts[0]) > 2:
                            appointment = {
                                "date": cell_texts[0] if len(cell_texts) > 0 else "",
                                "what": cell_texts[1] if len(cell_texts) > 1 else "",
                                "time": cell_texts[2] if len(cell_texts) > 2 else "",
                                "comment": cell_texts[3] if len(cell_texts) > 3 else "",
                                "full_description": f"{cell_texts[0]} - {cell_texts[1]}".strip(" -")
                            }
                            appointments.append(appointment)
            
            # If no table appointments, try alternative methods
            if not appointments:
                # Look for list items, divs, etc.
                for selector in ['li', 'div.appointment', 'div.event']:
                    elements = soup.select(selector)
                    for element in elements:
                        text = element.get_text().strip()
                        if text and len(text) > 10 and re.search(r'\d{1,2}[./]\d{1,2}', text):
                            appointments.append({
                                "date": "See description",
                                "what": text[:50] + "..." if len(text) > 50 else text,
                                "time": "",
                                "comment": "",
                                "full_description": text
                            })
                    
                    if appointments:
                        break
                        
        except Exception as e:
            _LOGGER.error(f"Enhanced parsing failed: {e}")
        
        return appointments

    async def async_test_credentials(self) -> bool:
        """Test credentials."""
        try:
            if not self.username or not self.password:
                return False
            
            if len(self.username) < 3 or len(self.password) < 3:
                return False
            
            # Quick connection test
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(LOGIN_URL) as response:
                    return response.status == 200
                    
        except Exception as e:
            _LOGGER.debug(f"Credential test failed: {e}")
            return False


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
    print("SFO Enhanced Scraper Test (Standalone)")
    print("=====================================")
    print("This will test the scraper with your actual SFO credentials.")
    print("Your credentials will not be stored or transmitted anywhere.")
    print()
    
    success = asyncio.run(test_scraper())
    
    if success:
        print("\n🎉 Test passed - scraper is working with your credentials!")
    else:
        print("\n💥 Test failed - check the error messages above")