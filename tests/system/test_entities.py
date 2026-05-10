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
    OraInteriorTempSensor,
    OraOdometerSensor,
    OraRangeSensor,
    OraSocSensor,
    OraTirePressureSensor,
)
from tests.fixtures.api_responses import VEHICLE_STATUS_RESPONSE


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

    vehicle = Vehicle(
        vin=vin,
        brand_name="ORA",
        app_show_series_name="Funky Cat",
        vtype="Funky Cat",
    )

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
        return OraSocSensor(coordinator, "LHG12345678901234")

    def test_native_value(self, sensor):
        """Test SOC value."""
        assert sensor.native_value == "75"

    def test_unique_id(self, sensor):
        """Test unique ID format."""
        assert sensor._attr_unique_id == "ora_LHG12345678901234_2013021"

    def test_device_class(self, sensor):
        """Test device class."""
        assert sensor._attr_device_class == "battery"


class TestOraRangeSensor:
    """Test Range sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        return OraRangeSensor(coordinator, "LHG12345678901234")

    def test_native_value(self, sensor):
        """Test range value."""
        assert sensor.native_value == "250"

    def test_unit(self, sensor):
        """Test unit."""
        assert sensor._attr_native_unit_of_measurement == "km"


class TestOraOdometerSensor:
    """Test Odometer sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        return OraOdometerSensor(coordinator, "LHG12345678901234")

    def test_native_value(self, sensor):
        """Test odometer value."""
        assert sensor.native_value == "15430"


class TestOraInteriorTempSensor:
    """Test Interior temperature sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        return OraInteriorTempSensor(coordinator, "LHG12345678901234")

    def test_native_value_divided_by_10(self, sensor):
        """Test temperature is divided by 10."""
        # API returns 215 (meaning 21.5°C)
        assert sensor.native_value == 21.5


class TestOraTirePressureSensor:
    """Test tire pressure sensors."""

    @pytest.mark.parametrize(
        "position,code",
        [("FL", 2101001), ("FR", 2101002), ("RL", 2101003), ("RR", 2101004)],
    )
    def test_tire_pressure(self, position, code):
        """Test tire pressure values."""
        coordinator = create_mock_coordinator()
        sensor = OraTirePressureSensor(coordinator, "LHG12345678901234", position, code)
        assert sensor.native_value == "230"

    @pytest.mark.parametrize("position", ["FL", "FR", "RL", "RR"])
    def test_tire_pressure_unit(self, position):
        """Test tire pressure unit."""
        coordinator = create_mock_coordinator()
        sensor = OraTirePressureSensor(coordinator, "LHG12345678901234", position, 2101001)
        assert sensor._attr_native_unit_of_measurement == "kPa"


class TestOraAcquisitionTimeSensor:
    """Test acquisition time sensor."""

    @pytest.fixture
    def sensor(self):
        coordinator = create_mock_coordinator()
        return OraAcquisitionTimeSensor(coordinator, "LHG12345678901234")

    def test_native_value_timestamp(self, sensor):
        """Test timestamp conversion."""
        result = sensor.native_value
        assert result is not None
        # 1704067200000 ms = 2024-01-01 00:00:00 UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1


class TestBinarySensors:
    """Test binary sensors."""

    def test_ac_sensor_on(self):
        """Test A/C is on."""
        coordinator = create_mock_coordinator()
        sensor = OraAcBinarySensor(coordinator, "LHG12345678901234")
        assert sensor.is_on is True

    def test_lock_sensor_on(self):
        """Test lock is on (locked)."""
        coordinator = create_mock_coordinator()
        sensor = OraLockBinarySensor(coordinator, "LHG12345678901234")
        assert sensor.is_on is True

    def test_charge_plug_sensor_on(self):
        """Test charge plug is connected."""
        coordinator = create_mock_coordinator()
        sensor = OraChargePlugBinarySensor(coordinator, "LHG12345678901234")
        assert sensor.is_on is True

    @pytest.mark.parametrize(
        "position,code",
        [("FL", 2210001), ("FR", 2210002), ("RL", 2210003), ("RR", 2210004)],
    )
    def test_window_closed(self, position, code):
        """Test windows are closed (value=1 means closed)."""
        coordinator = create_mock_coordinator()
        sensor = OraWindowBinarySensor(coordinator, "LHG12345678901234", position, code)
        # payload_off = "1", and value is "1", so is_on = False (closed)
        assert sensor.is_on is False


class TestOraDeviceTracker:
    """Test device tracker."""

    @pytest.fixture
    def tracker(self):
        coordinator = create_mock_coordinator()
        return OraDeviceTracker(coordinator, "LHG12345678901234", "Funky Cat")

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


class TestEntityWithNoData:
    """Test entities with no data."""

    def test_sensor_with_no_data(self):
        """Test sensor returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        sensor = OraSocSensor(coordinator, "LHG12345678901234")
        assert sensor.native_value is None

    def test_binary_sensor_with_no_data(self):
        """Test binary sensor returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        sensor = OraAcBinarySensor(coordinator, "LHG12345678901234")
        assert sensor.is_on is None

    def test_device_tracker_with_no_data(self):
        """Test device tracker returns None when no data."""
        coordinator = MagicMock()
        coordinator.data = {}

        tracker = OraDeviceTracker(coordinator, "LHG12345678901234", "Test")
        assert tracker.latitude is None
        assert tracker.longitude is None
