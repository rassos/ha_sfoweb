"""Constants for the SFOWeb integration."""
from typing import Final

DOMAIN: Final = "sfoweb"
NAME: Final = "SFOWeb"

# URLs
LOGIN_URL: Final = "https://soestjernen.sfoweb.dk/redirect.php?id=441&loginmethod=ParentTabulexLogin"
APPOINTMENTS_URL: Final = "https://soestjernen.sfoweb.dk/guardian/appointments"

# Selectors
USERNAME_SELECTOR: Final = 'input#username'
PASSWORD_SELECTOR: Final = 'input#password'
SUBMIT_SELECTOR: Final = 'button[type="submit"]'
PARENT_LOGIN_SELECTOR: Final = 'a[href*="ParentTabulexLogin"]'
APPOINTMENTS_TABLE_SELECTOR: Final = 'table.table-striped > tbody > tr'

# Configuration
DEFAULT_SCAN_INTERVAL: Final = 6  # hours
