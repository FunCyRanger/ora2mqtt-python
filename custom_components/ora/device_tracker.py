"""Device tracker for GWM ORA vehicles."""

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker."""
    coordinator = hass.data["ora"][config_entry.entry_id]

    added_vins: set[str] = set()

    def add_entities():
        """Add entities when coordinator has data."""
        if not coordinator.data:
            return

        entities = []
        for vin in coordinator.data:
            if vin in added_vins:
                continue
            data = coordinator.data.get(vin)
            if data:
                added_vins.add(vin)
                entities.append(
                    create_device_tracker_for_vehicle(
                        coordinator, vin, data.vehicle.app_show_series_name or "ORA Vehicle"
                    )
                )

        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(add_entities)

    if coordinator.data:
        add_entities()


class OraDeviceTracker(TrackerEntity):
    """Device tracker for ORA vehicle."""

    def __init__(self, coordinator: OraCoordinator, vin: str, name: str):
        self._coordinator = coordinator
        self._vin = vin
        self._attr_name = name
        self._attr_unique_id = f"ora_{vin}_tracker"

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        data = self._coordinator.data.get(self._vin)
        if data and data.status:
            return data.status.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        data = self._coordinator.data.get(self._vin)
        if data and data.status:
            return data.status.longitude
        return None

    @property
    def source_type(self) -> str:
        """Return source type."""
        return "gps"

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra state attributes."""
        data = self._coordinator.data.get(self._vin)
        if not data or not data.status:
            return None

        return {
            "vin": self._vin,
            "device_id": data.status.device_id,
            "acquisition_time": data.status.acquisition_time,
            "update_time": data.status.update_time,
        }


def create_device_tracker_for_vehicle(
    coordinator: OraCoordinator, vin: str, name: str
) -> OraDeviceTracker:
    """Create device tracker for a vehicle."""
    return OraDeviceTracker(coordinator, vin, name)
