"""The SFO Appointments integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .scraper import SFOScraper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)  # Check every 6 hours


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFO Appointments from a config entry."""
    
    # Create the scraper
    scraper = SFOScraper(
        username=entry.data["username"],
        password=entry.data["password"]
    )
    
    # Create coordinator
    coordinator = SFOAppointmentsDataUpdateCoordinator(hass, scraper)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class SFOAppointmentsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the SFO system."""

    def __init__(self, hass: HomeAssistant, scraper: SFOScraper) -> None:
        """Initialize."""
        self.scraper = scraper
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            return await self.scraper.async_get_appointments()
        except Exception as exception:
            raise UpdateFailed(exception) from exception
