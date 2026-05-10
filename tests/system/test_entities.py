"""System tests for entity classes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.ora.api import Vehicle, VehicleStatus, VehicleStatusItem
from custom_components.ora.binary_sensor import (
    OraAcBinarySensor,
    OraChargePlugBinarySensor,
    OraLockBinarySensor,
    OraWindowBinarySensor,
)
from custom_components.ora.coordinator import VehicleData
from custom_components.ora.device_tracker import OraDeviceTracker
from custom_components.ora.sensor import (
    OraAcquisitionTimeSensor,
    OraChargingTimeSensor,
    OraInteriorTempSensor,
    OraOdometerSensor,
    OraRangeSensor,
    OraSocSensor,
    OraSocTargetSensor,
    OraTirePressureSensor,
)
from tests.fixtures.api_responses import VEHICLE_STATUS_RESPONSE


def create_mock_vehicle(vin="LHG12345678901234"):
    """Create a mock vehicle."""
    return Vehicle(
        vin=vin,
        brand_name="ORA",
        app_show_series_name="Funky Cat",
        vtype="Funky Cat",
    )


def create_mock_coordinator(vin="LHG12345678901234"):
    """Create a mock coordinator with vehicle data."""
    status_data = VEHICLE_STATUS_RESPONSE["data"]

    status = VehicleStatus(
        vin=vin,
        acquisition_time=status_data["acquisitionTime"],
        update_time=status_data["updateTime"],
        device_id=status_data["deviceId"],
        latitude=status_data["latitude"],
        longitude=status_data["longitude"],
        items=[
            VehicleStatusItem(
                code=int(item["code"]),
                value=item["value"],
                unit=item.get("unit"),
            )
            for item in status_data["items"]
        ],
    )

    vehicle = create_mock_vehicle(vin)

    coordinator = MagicMock()
    coordinator.data = {
        vin: VehicleData(
            vehicle=vehicle,
            status=status,
            last_update=datetime.now(timezone.utc),
        )
    }

    return coordinator


class TestOraSocSensor:
    """Test SOC sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraSocSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value(self, sensor):
        """Test SOC value."""
        assert sensor.native_value == "75"

    def test_unique_id(self, sensor):
        """Test unique ID format."""
        assert sensor._attr_unique_id == "ora_LHG12345678901234_2013021"

    def test_device_class(self, sensor):
        """Test device class."""
        assert sensor._attr_device_class == "battery"

    def test_device_info(self, sensor):
        """Test device_info is set."""
        assert sensor._attr_device_info is not None
        assert sensor._attr_device_info["identifiers"] == {("ora", "LHG12345678901234")}
        assert sensor._attr_device_info["manufacturer"] == "GWM"
        assert sensor._attr_device_info["model"] == "Funky Cat"
        assert sensor._attr_device_info["serial_number"] == "LHG12345678901234"
        assert sensor._attr_device_info["name"] == "Funky Cat"


class TestOraRangeSensor:
    """Test Range sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraRangeSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value(self, sensor):
        """Test range value."""
        assert sensor.native_value == "250"

    def test_unit(self, sensor):
        """Test unit."""
        assert sensor._attr_native_unit_of_measurement == "km"


class TestOraChargingTimeSensor:
    """Test Charging Time Remaining sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraChargingTimeSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value(self, sensor):
        """Test charging time value."""
        assert sensor.native_value == "30"

    def test_unit(self, sensor):
        """Test unit."""
        assert sensor._attr_native_unit_of_measurement == "min"


class TestOraSocTargetSensor:
    """Test SOC Target sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraSocTargetSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value(self, sensor):
        """Test SOC target value."""
        assert sensor.native_value == "80"

    def test_device_class(self, sensor):
        """Test device class."""
        assert sensor._attr_device_class == "battery"

    def test_unit(self, sensor):
        """Test unit."""
        assert sensor._attr_native_unit_of_measurement == "%"


class TestOraOdometerSensor:
    """Test Odometer sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraOdometerSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value(self, sensor):
        """Test odometer value."""
        assert sensor.native_value == "15430"


class TestOraInteriorTempSensor:
    """Test Interior temperature sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraInteriorTempSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value_divided_by_10(self, sensor):
        """Test temperature is divided by 10."""
        assert sensor.native_value == 21.5


class TestOraTirePressureSensor:
    """Test tire pressure sensors."""

    @pytest.fixture
    def coordinator(self):
        return create_mock_coordinator()

    @pytest.fixture
    def vehicle(self):
        return create_mock_vehicle()

    @pytest.mark.parametrize(
        "position,code,expected",
        [
            ("FL", 2101001, "230"),
            ("FR", 2101002, "230"),
            ("RL", 2101003, "235"),
            ("RR", 2101004, "235"),
        ],
    )
    def test_tire_pressure(self, coordinator, vehicle, position, code, expected):
        """Test tire pressure values."""
        sensor = OraTirePressureSensor(coordinator, "LHG12345678901234", vehicle, position, code)
        assert sensor.native_value == expected

    @pytest.mark.parametrize("position", ["FL", "FR", "RL", "RR"])
    def test_tire_pressure_unit(self, coordinator, vehicle, position):
        """Test tire pressure unit."""
        sensor = OraTirePressureSensor(coordinator, "LHG12345678901234", vehicle, position, 2101001)
        assert sensor._attr_native_unit_of_measurement == "kPa"


class TestOraAcquisitionTimeSensor:
    """Test acquisition time sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraAcquisitionTimeSensor(coordinator, "LHG12345678901234", vehicle)

    def test_native_value_timestamp(self, sensor):
        """Test timestamp conversion."""
        result = sensor.native_value
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1


class TestBinarySensors:
    """Test binary sensors."""

    @pytest.fixture
    def vehicle(self):
        return create_mock_vehicle()

    def test_ac_sensor_on(self, vehicle):
        """Test A/C is on."""
        coordinator = create_mock_coordinator()
        sensor = OraAcBinarySensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor.is_on is True

    def test_lock_sensor_on(self, vehicle):
        """Test lock is on (locked)."""
        coordinator = create_mock_coordinator()
        sensor = OraLockBinarySensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor.is_on is True

    def test_charge_plug_sensor_on(self, vehicle):
        """Test charge plug is connected."""
        coordinator = create_mock_coordinator()
        sensor = OraChargePlugBinarySensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor.is_on is True

    @pytest.mark.parametrize(
        "position,code",
        [("FL", 2210001), ("FR", 2210002), ("RL", 2210003), ("RR", 2210004)],
    )
    def test_window_closed(self, vehicle, position, code):
        """Test windows are closed (value=1 means closed)."""
        coordinator = create_mock_coordinator()
        sensor = OraWindowBinarySensor(coordinator, "LHG12345678901234", vehicle, position, code)
        assert sensor.is_on is False

    def test_binary_sensor_device_info(self, vehicle):
        """Test binary sensor device_info is set."""
        coordinator = create_mock_coordinator()
        sensor = OraAcBinarySensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor._attr_device_info is not None
        assert sensor._attr_device_info["identifiers"] == {("ora", "LHG12345678901234")}
        assert sensor._attr_device_info["manufacturer"] == "GWM"


class TestOraDeviceTracker:
    """Test device tracker."""

    @pytest.fixture
    def tracker(self):
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        return OraDeviceTracker(coordinator, "LHG12345678901234", vehicle)

    def test_latitude(self, tracker):
        """Test latitude."""
        assert tracker.latitude == 52.520008

    def test_longitude(self, tracker):
        """Test longitude."""
        assert tracker.longitude == 13.404954

    def test_source_type(self, tracker):
        """Test source type."""
        assert tracker.source_type == "gps"

    def test_extra_state_attributes(self, tracker):
        """Test extra state attributes."""
        attrs = tracker.extra_state_attributes
        assert attrs["vin"] == "LHG12345678901234"
        assert "acquisition_time" in attrs
        assert "update_time" in attrs

    def test_device_info(self, tracker):
        """Test device tracker device_info is set."""
        assert tracker._attr_device_info is not None
        assert tracker._attr_device_info["identifiers"] == {("ora", "LHG12345678901234")}
        assert tracker._attr_device_info["manufacturer"] == "GWM"
        assert tracker._attr_device_info["model"] == "Funky Cat"
        assert tracker._attr_device_info["name"] == "Funky Cat"


class TestEntityWithNoData:
    """Test entities with no data."""

    @pytest.fixture
    def vehicle(self):
        return create_mock_vehicle()

    def test_sensor_with_no_data(self, vehicle):
        """Test sensor returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        sensor = OraSocSensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor.native_value is None

    def test_binary_sensor_with_no_data(self, vehicle):
        """Test binary sensor returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        sensor = OraAcBinarySensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor.is_on is None

    def test_device_tracker_with_no_data(self, vehicle):
        """Test device tracker returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        tracker = OraDeviceTracker(coordinator, "LHG12345678901234", vehicle)
        assert tracker.latitude is None
        assert tracker.longitude is None


class TestDeviceInfoConsistency:
    """Test that all entities for the same VIN share the same device identifier."""

    def test_all_entities_share_same_device_identifier(self):
        """All entities should have identical identifiers for the same VIN."""
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        vin = "LHG12345678901234"

        sensor = OraSocSensor(coordinator, vin, vehicle)
        binary_sensor = OraAcBinarySensor(coordinator, vin, vehicle)
        tracker = OraDeviceTracker(coordinator, vin, vehicle)

        sensor_id = sensor._attr_device_info["identifiers"]
        binary_id = binary_sensor._attr_device_info["identifiers"]
        tracker_id = tracker._attr_device_info["identifiers"]

        assert sensor_id == binary_id == tracker_id == {("ora", vin)}

    def test_device_info_reflects_vehicle_name(self):
        """Device info name should match vehicle app_show_series_name."""
        coordinator = create_mock_coordinator()
        vehicle = create_mock_vehicle()
        vehicle.app_show_series_name = "My Cool Car"
        vehicle.vtype = "Cool Cat"

        sensor = OraSocSensor(coordinator, "LHG12345678901234", vehicle)
        assert sensor._attr_device_info["name"] == "My Cool Car"
        assert sensor._attr_device_info["model"] == "Cool Cat"

