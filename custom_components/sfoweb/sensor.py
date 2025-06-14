"""Support for SFOWeb sensors."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SFOWeb sensor."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    username = config_entry.data[CONF_USERNAME]
    
    sensors = [
        SFOWebTestSensor(coordinator, username),
    ]
    
    async_add_entities(sensors, update_before_add=True)


class SFOWebTestSensor(CoordinatorEntity, SensorEntity):
    """Test sensor to verify integration works."""

    def __init__(self, coordinator, username: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._username = username
        self._attr_name = f"SFOWeb Test ({username})"
        self._attr_unique_id = f"sfoweb_test_{username}"
        self._attr_icon = "mdi:calendar-check"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return "No data"
        return f"Found {len(self.coordinator.data)} appointments"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        
        return {
            "appointments": self.coordinator.data,
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True
