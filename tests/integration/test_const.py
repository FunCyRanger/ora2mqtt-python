"""Integration tests for constants and data points."""


from custom_components.ora.const import (
    BINARY_SENSORS,
    CONF_ACCOUNT_ACCESS_TOKEN,
    CONF_ACCOUNT_DEVICE_ID,
    CONF_ACCOUNT_PHONE,
    CONF_ACCOUNT_REFRESH_TOKEN,
    DATA_POINTS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    REGIONS,
)


class TestConstants:
    """Test constant values."""

    def test_domain(self):
        """Test domain is set correctly."""
        assert DOMAIN == "ora"

    def test_default_poll_interval(self):
        """Test default poll interval."""
        assert DEFAULT_POLL_INTERVAL == 60

    def test_config_keys(self):
        """Test config keys are defined."""
        assert CONF_ACCOUNT_PHONE == "phone"
        assert CONF_ACCOUNT_ACCESS_TOKEN == "access_token"
        assert CONF_ACCOUNT_REFRESH_TOKEN == "refresh_token"
        assert CONF_ACCOUNT_DEVICE_ID == "device_id"


class TestDataPoints:
    """Test data point definitions."""

    def test_data_points_count(self):
        """Test we have data points defined."""
        assert len(DATA_POINTS) > 0

    def test_data_points_format(self):
        """Test data points have correct format."""
        for code, (attr, unit, name) in DATA_POINTS.items():
            assert isinstance(code, int)
            assert isinstance(attr, str)
            assert isinstance(name, str)
            assert unit is None or isinstance(unit, str)

    def test_required_sensors_present(self):
        """Test that all required sensors are defined."""
        required_codes = [2013021, 2011501, 2103010, 2041301, 2201001]
        for code in required_codes:
            assert code in DATA_POINTS, f"Missing required sensor code {code}"

    def test_tire_pressure_codes(self):
        """Test tire pressure codes are defined."""
        tire_pressure_codes = [2101001, 2101002, 2101003, 2101004]
        for code in tire_pressure_codes:
            assert code in DATA_POINTS
            attr, unit, name = DATA_POINTS[code]
            assert "pressure" in attr.lower()
            assert unit == "kPa"

    def test_tire_temperature_codes(self):
        """Test tire temperature codes are defined."""
        tire_temp_codes = [2101005, 2101006, 2101007, 2101008]
        for code in tire_temp_codes:
            assert code in DATA_POINTS
            attr, unit, name = DATA_POINTS[code]
            assert "temp" in attr.lower()
            assert unit == "°C"

    def test_window_codes(self):
        """Test window codes are defined."""
        window_codes = [2210001, 2210002, 2210003, 2210004]
        for code in window_codes:
            assert code in DATA_POINTS


class TestBinarySensors:
    """Test binary sensor mappings."""

    def test_binary_sensors_count(self):
        """Test we have binary sensors defined."""
        assert len(BINARY_SENSORS) > 0

    def test_binary_sensors_format(self):
        """Test binary sensors have correct format."""
        for code, (attr, device_class, payload_on, payload_off) in BINARY_SENSORS.items():
            assert isinstance(code, int)
            assert isinstance(attr, str)
            assert device_class is None or isinstance(device_class, str)
            assert isinstance(payload_on, str)
            assert isinstance(payload_off, str)

    def test_ac_binary_sensor(self):
        """Test A/C binary sensor."""
        assert 2202001 in BINARY_SENSORS
        attr, device_class, on, off = BINARY_SENSORS[2202001]
        assert attr == "ac"
        assert device_class == "running"

    def test_lock_binary_sensor(self):
        """Test lock binary sensor."""
        assert 2208001 in BINARY_SENSORS
        attr, device_class, on, off = BINARY_SENSORS[2208001]
        assert attr == "lock"
        assert device_class == "lock"

    def test_charge_plug_binary_sensor(self):
        """Test charge plug binary sensor."""
        assert 2042082 in BINARY_SENSORS
        attr, device_class, on, off = BINARY_SENSORS[2042082]
        assert attr == "charge_plug"
        assert device_class == "plug"

    def test_window_binary_sensors(self):
        """Test window binary sensors."""
        window_codes = [2210001, 2210002, 2210003, 2210004]
        for code in window_codes:
            assert code in BINARY_SENSORS
            attr, device_class, on, off = BINARY_SENSORS[code]
            assert "window" in attr.lower()
            assert device_class == "window"
            assert on == "3"
            assert off == "1"


class TestRegions:
    """Test region configurations."""

    def test_eu_region_present(self):
        """Test EU region is defined."""
        assert "eu" in REGIONS

    def test_eu_endpoints(self):
        """Test EU endpoints are defined."""
        eu = REGIONS["eu"]
        assert "h5_gateway" in eu
        assert "app_gateway" in eu
        assert "data_upload_gateway" in eu
        assert "common_gateway" in eu

    def test_eu_gateway_format(self):
        """Test EU gateway URLs are formatted correctly."""
        eu = REGIONS["eu"]
        assert eu["h5_gateway"] == "eu-h5-gateway.gwmcloud.com"
        assert eu["app_gateway"] == "eu-app-gateway.gwmcloud.com"
        assert ".gwmcloud.com" in eu["h5_gateway"]


class TestDataPointCoverage:
    """Test coverage of data points vs binary sensors."""

    def test_all_binary_codes_in_data_points(self):
        """Test all binary sensor codes exist in data points."""
        for code in BINARY_SENSORS:
            assert code in DATA_POINTS, f"Binary sensor code {code} not in data points"

    def test_coverage_documentation(self):
        """Test that README data points are covered."""
        # These are from the README
        expected_codes = [
            2011501,  # Range
            2013021,  # SOC
            2013022,  # Charging time remaining
            2041142,  # Charging active
            2041301,  # SOCE
            2078020,  # Air circulation
            2101001,  # Tire pressure vl
            2101002,  # Tire pressure vr
            2101003,  # Tire pressure hl
            2101004,  # Tire pressure hr
            2101005,  # Tire temp vl
            2101006,  # Tire temp vr
            2101007,  # Tire temp hl
            2101008,  # Tire temp hr
            2103010,  # Odometer
            2201001,  # Interior temp
            2202001,  # A/C
            2208001,  # Lock
            2210001,  # Window vl
            2210002,  # Window vr
            2210003,  # Window hl
            2210004,  # Window hr
            2222001,  # Front defroster
            2042082,  # Charge plug
        ]

        for code in expected_codes:
            assert code in DATA_POINTS, f"Missing README data point {code}"
