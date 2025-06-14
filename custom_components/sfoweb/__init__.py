"""The SFOWeb integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .scraper import SFOScraper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFOWeb from a config entry."""
    
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    scraper = SFOScraper(username, password)
    coordinator = SFOWebDataUpdateCoordinator(hass, scraper)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class SFOWebDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from SFOWeb."""

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
        """Update data via scraper."""
        try:
            return await self.scraper.async_get_appointments()
        except Exception as exception:
            raise UpdateFailed(f"Error communicating with SFOWeb: {exception}") from exception
