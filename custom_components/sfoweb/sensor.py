"""Support for SFOWeb sensors."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
        SFOWebAppointmentsSensor(coordinator, username),
        SFOWebNextAppointmentSensor(coordinator, username),
    ]
    
    async_add_entities(sensors, update_before_add=True)


class SFOWebAppointmentsSensor(CoordinatorEntity, SensorEntity):
    """Representation of SFOWeb appointments sensor."""

    def __init__(self, coordinator, username: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._username = username
        self._attr_name = f"SFOWeb Appointments ({username})"
        self._attr_unique_id = f"sfoweb_appointments_{username}"
        self._attr_icon = "mdi:calendar-check"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        
        attributes = {
            "appointments": [],
            "last_updated": datetime.now().isoformat(),
        }
        
        for appointment in self.coordinator.data:
            attributes["appointments"].append({
                "date": appointment["date"],
                "time": appointment["time"],
                "what": appointment["what"],
                "comment": appointment["comment"],
                "description": appointment["full_description"],
            })
        
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success


class SFOWebNextAppointmentSensor(CoordinatorEntity, SensorEntity):
    """Representation of next SFOWeb appointment sensor."""

    def __init__(self, coordinator, username: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._username = username
        self._attr_name = f"SFOWeb Next Appointment ({username})"
        self._attr_unique_id = f"sfoweb_next_appointment_{username}"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "No appointments"
        
        # Return the first appointment (assuming they're in chronological order)
        next_appointment = self.coordinator.data[0]
        return next_appointment["full_description"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {"last_updated": datetime.now().isoformat()}
        
        next_appointment = self.coordinator.data[0]
        return {
            "date": next_appointment["date"],
            "time": next_appointment["time"],
            "what": next_appointment["what"],
            "comment": next_appointment["comment"],
            "last_updated": datetime.now().isoformat(),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
