"""Binary sensor entities for GWM ORA."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OraCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
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
            added_vins.add(vin)
            entities.extend(create_binary_sensors_for_vehicle(coordinator, vin))

        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(add_entities)

    if coordinator.data:
        add_entities()


class OraBinarySensor(BinarySensorEntity):
    """Generic ORA binary sensor."""

    def __init__(
        self,
        coordinator: OraCoordinator,
        vehicle_vin: str,
        data_code: int,
        name: str,
        device_class: BinarySensorDeviceClass | None = None,
        payload_on: str = "1",
        payload_off: str = "0",
    ):
        self._coordinator = coordinator
        self._vehicle_vin = vehicle_vin
        self._data_code = data_code
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_unique_id = f"ora_{vehicle_vin}_binary_{data_code}"

    @property
    def is_on(self) -> bool | None:
        """Return the sensor state."""
        data = self._coordinator.data.get(self._vehicle_vin)
        if not data or not data.status or not data.status.items:
            return None

        for item in data.status.items:
            if item.code == self._data_code:
                return str(item.value) == self._payload_on
        return None


class OraAcBinarySensor(OraBinarySensor):
    """A/C binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2202001,
            "A/C",
            device_class=BinarySensorDeviceClass.RUNNING,
        )


class OraLockBinarySensor(OraBinarySensor):
    """Lock binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2208001,
            "Lock",
            device_class=BinarySensorDeviceClass.LOCK,
        )


class OraChargePlugBinarySensor(OraBinarySensor):
    """Charge plug binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2042082,
            "Charge Plug",
            device_class=BinarySensorDeviceClass.PLUG,
        )


class OraChargingActiveBinarySensor(OraBinarySensor):
    """Charging active binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2041142,
            "Charging Active",
            device_class=BinarySensorDeviceClass.HEAT,
        )


class OraAirCirculationBinarySensor(OraBinarySensor):
    """Air circulation binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2078020,
            "Air Circulation",
            device_class=BinarySensorDeviceClass.RUNNING,
        )


class OraDefrosterFrontBinarySensor(OraBinarySensor):
    """Front defroster binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2222001,
            "Front Defroster",
            device_class=BinarySensorDeviceClass.HEAT,
        )


class OraWindowBinarySensor(OraBinarySensor):
    """Window binary sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str, position: str, code: int):
        super().__init__(
            coordinator,
            vin,
            code,
            f"Window {position}",
            device_class=BinarySensorDeviceClass.WINDOW,
            payload_on="3",
            payload_off="1",
        )


def create_binary_sensors_for_vehicle(
    coordinator: OraCoordinator, vin: str
) -> list[BinarySensorEntity]:
    """Create all binary sensor entities for a vehicle."""
    return [
        OraAcBinarySensor(coordinator, vin),
        OraLockBinarySensor(coordinator, vin),
        OraChargePlugBinarySensor(coordinator, vin),
        OraChargingActiveBinarySensor(coordinator, vin),
        OraAirCirculationBinarySensor(coordinator, vin),
        OraDefrosterFrontBinarySensor(coordinator, vin),
        OraWindowBinarySensor(coordinator, vin, "FL", 2210001),
        OraWindowBinarySensor(coordinator, vin, "FR", 2210002),
        OraWindowBinarySensor(coordinator, vin, "RL", 2210003),
        OraWindowBinarySensor(coordinator, vin, "RR", 2210004),
    ]
