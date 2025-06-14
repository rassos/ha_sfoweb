"""The SFOWeb integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)  # Check every 6 hours


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFOWeb from a config entry."""
    
    # Create a simple coordinator for now
    coordinator = SimpleDataUpdateCoordinator(hass)
    
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


class SimpleDataUpdateCoordinator(DataUpdateCoordinator):
    """Simple coordinator for testing."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data."""
        # Return dummy data for now
        return [
            {
                "date": "2025-06-12",
                "what": "Selvbestemmer",
                "time": "14:00-16:00",
                "comment": "Test appointment",
                "full_description": "2025-06-12 - 14:00-16:00"
            }
        ]
