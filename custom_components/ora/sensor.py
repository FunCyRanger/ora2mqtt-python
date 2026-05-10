"""Sensor entities for GWM ORA."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    """Set up sensors."""
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
            entities.extend(create_sensors_for_vehicle(coordinator, vin))

        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(add_entities)

    if coordinator.data:
        add_entities()


class OraSensor(SensorEntity):
    """Generic ORA sensor."""

    def __init__(
        self,
        coordinator: OraCoordinator,
        vehicle_vin: str,
        data_code: int,
        name: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
    ):
        self._coordinator = coordinator
        self._vehicle_vin = vehicle_vin
        self._data_code = data_code
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_name = name
        self._attr_unique_id = f"ora_{vehicle_vin}_{data_code}"

    @property
    def native_value(self):
        """Return the sensor value."""
        data = self._coordinator.data.get(self._vehicle_vin)
        if not data or not data.status or not data.status.items:
            return None

        for item in data.status.items:
            if item.code == self._data_code:
                return item.value
        return None


class OraSocSensor(OraSensor):
    """SOC (State of Charge) sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2013021,
            "SOC",
            device_class=SensorDeviceClass.BATTERY,
            unit="%",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraRangeSensor(OraSensor):
    """Range sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2011501,
            "Range",
            device_class=SensorDeviceClass.DISTANCE,
            unit="km",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraOdometerSensor(OraSensor):
    """Odometer sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2103010,
            "Odometer",
            device_class=SensorDeviceClass.DISTANCE,
            unit="km",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraSoceSensor(OraSensor):
    """SOCE (State of Charge Energy) sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2041301,
            "SOCE",
            unit="%",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraInteriorTempSensor(OraSensor):
    """Interior temperature sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            2201001,
            "Interior Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit="°C",
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self):
        """Return the value divided by 10."""
        val = super().native_value
        if val is not None:
            try:
                return int(val) / 10
            except (TypeError, ValueError):
                pass
        return None


class OraTirePressureSensor(OraSensor):
    """Tire pressure sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str, position: str, code: int):
        super().__init__(
            coordinator,
            vin,
            code,
            f"Tire Pressure {position}",
            device_class=SensorDeviceClass.PRESSURE,
            unit="kPa",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraTireTempSensor(OraSensor):
    """Tire temperature sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str, position: str, code: int):
        super().__init__(
            coordinator,
            vin,
            code,
            f"Tire Temperature {position}",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit="°C",
            state_class=SensorStateClass.MEASUREMENT,
        )


class OraAcquisitionTimeSensor(OraSensor):
    """Acquisition time sensor."""

    def __init__(self, coordinator: OraCoordinator, vin: str):
        super().__init__(
            coordinator,
            vin,
            0,  # Special - not a data point
            "Acquisition Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        )

    @property
    def native_value(self):
        """Return the acquisition time as timestamp."""
        data = self._coordinator.data.get(self._vehicle_vin)
        if not data or not data.status:
            return None

        from datetime import datetime, timezone

        try:
            # Convert milliseconds to datetime
            return datetime.fromtimestamp(data.status.acquisition_time / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            return None


def create_sensors_for_vehicle(coordinator: OraCoordinator, vin: str) -> list[SensorEntity]:
    """Create all sensor entities for a vehicle."""
    return [
        OraSocSensor(coordinator, vin),
        OraRangeSensor(coordinator, vin),
        OraOdometerSensor(coordinator, vin),
        OraSoceSensor(coordinator, vin),
        OraInteriorTempSensor(coordinator, vin),
        OraAcquisitionTimeSensor(coordinator, vin),
        OraTirePressureSensor(coordinator, vin, "FL", 2101001),
        OraTirePressureSensor(coordinator, vin, "FR", 2101002),
        OraTirePressureSensor(coordinator, vin, "RL", 2101003),
        OraTirePressureSensor(coordinator, vin, "RR", 2101004),
        OraTireTempSensor(coordinator, vin, "FL", 2101005),
        OraTireTempSensor(coordinator, vin, "FR", 2101006),
        OraTireTempSensor(coordinator, vin, "RL", 2101007),
        OraTireTempSensor(coordinator, vin, "RR", 2101008),
    ]
