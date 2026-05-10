"""Shared test fixtures and configuration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_ora_integration():
    """Mock ORA integration for testing."""
    import pathlib

    from custom_components.ora import DOMAIN, config_flow

    class MockManifest(dict):
        def __init__(self):
            super().__init__(
                {
                    "domain": DOMAIN,
                    "name": "GWM ORA",
                    "config_flow": True,
                    "dependencies": [],
                    "requirements": [],
                    "codeowners": [],
                    "is_built_in": False,
                    "overwrites_built_in": False,
                    "integration_type": "device",
                }
            )

    class MockIntegration:
        domain = DOMAIN
        name = "ORA"
        pkg_path = "custom_components.ora"
        file_path = pathlib.Path("custom_components/ora")
        manifest = MockManifest()
        _platforms_to_preload = []
        _all_dependencies = set()
        after_dependencies = []
        mqtt = []
        disabled = None
        has_translations = False
        import_executor = False
        documentation = ""
        issue_tracker = ""
        quality_scale = None
        loggers = []
        top_level_files = set()
        ssdp = []
        zeroconf = []
        homekit = {}
        dhcp = []
        bluetooth = []
        energy = None
        iot_class = "local_polling"

        def __init__(self):
            self._component_future = None
            self._import_futures = {}

        async def async_resolve_dependencies(self):
            return True

        async def resolve_dependencies(self, *args):
            return True

        async def async_get_components(self):
            from custom_components.ora import config_flow

            return config_flow

        async def async_get_component(self):
            import importlib

            return importlib.import_module("custom_components.ora")

        async def async_get_platform(self, platform_name):
            if platform_name == "config_flow":
                return config_flow.ConfigFlow
            return None

        @property
        def is_built_in(self):
            return False

        @property
        def overwrites_built_in(self):
            return False

        @property
        def config_flow(self):
            return config_flow.ConfigFlow

        @property
        def dependencies(self):
            return []

        @property
        def integration_type(self):
            return "device"

    mock_integration = MockIntegration()

    async def mock_async_get_custom_components(hass):
        return {DOMAIN: mock_integration}

    async def mock_async_get_integration(hass, domain):
        if domain == DOMAIN:
            return mock_integration
        if domain == "mqtt":

            class MockMqttIntegration:
                domain = "mqtt"
                name = "MQTT"
                pkg_path = "homeassistant.components.mqtt"
                manifest = {
                    "domain": "mqtt",
                    "name": "MQTT",
                    "dependencies": [],
                    "requirements": [],
                }

                @property
                def config_flow(self):
                    return None

            return MockMqttIntegration()
        from homeassistant.loader import IntegrationNotFound

        raise IntegrationNotFound(domain)

    async def mock_async_get_integration_with_requirements(hass, domain):
        if domain == DOMAIN:
            return mock_integration
        from homeassistant.requirements import RequirementsNotFound

        raise RequirementsNotFound(domain, "requirements")

    with patch(
        "homeassistant.loader.async_get_custom_components", mock_async_get_custom_components
    ):
        with patch("homeassistant.loader.async_get_integration", mock_async_get_integration):
            with patch(
                "homeassistant.requirements.async_get_integration_with_requirements",
                mock_async_get_integration_with_requirements,
            ):
                yield mock_integration


class MockConfigEntry:
    def __init__(self, entry_id="test", data=None):
        self.entry_id = entry_id
        self.data = data or {}
        self.config_entries = MagicMock()
        self.config_entries.async_update_entry = AsyncMock()


class MockPlatform:
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    DEVICE_TRACKER = "device_tracker"


class MockHomeAssistant:
    def __init__(self):
        self.data = {}
        self.config_entries = MagicMock()
        self.config_entries.async_update_entry = AsyncMock()
        self.config_entries.async_forward_entry_setups = AsyncMock()


@pytest.fixture
def mock_cert_dir(tmp_path):
    """Create a temporary certificate directory."""
    cert_dir = tmp_path / "cert"
    cert_dir.mkdir()
    return cert_dir


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    from custom_components.ora.api import GwmApi

    client = MagicMock(spec=GwmApi)
    client.auth = MagicMock()
    client.vehicles = MagicMock()
    client.set_access_token = MagicMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    return MockHomeAssistant()


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        entry_id="test_entry_123",
        data={
            "phone": "+491234567890",
            "device_id": "test_device_456",
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "region": "eu",
            "poll_interval": 60,
        },
    )


@pytest.fixture
def mock_coordinator_data():
    """Create mock coordinator data."""
    from tests.fixtures.api_responses import VEHICLE_STATUS_RESPONSE

    return {
        "LHG12345678901234": {
            "vehicle": {
                "vin": "LHG12345678901234",
                "brand_name": "ORA",
                "app_show_series_name": "Funky Cat",
                "vtype": "Funky Cat",
            },
            "status": VEHICLE_STATUS_RESPONSE["data"],
            "last_update": None,
        }
    }


@pytest.fixture(autouse=True)
def patch_certificates():
    """Auto-patch certificate loading in tests."""
    with MagicMock():
        yield


@pytest.fixture(autouse=True)
def prevent_entry_setup():
    """Prevent HA from setting up integration after config flow creates entry.

    E2E flow tests verify flow results, not runtime setup. This avoids needing
    to implement the full Integration interface.
    """
    original_async_setup = None

    async def mock_async_add(self, entry, *args, **kwargs):
        nonlocal original_async_setup
        self._entries[entry.entry_id] = entry
        self.async_update_issues()
        self._async_dispatch.__wrapped__(
            self,
            entry.__class__.__bases__[0].__bases__[0](
                entry.__class__.__bases__[0].__bases__[0].ADDED, entry
            ),
        )
        self._async_schedule_save()

    with patch("homeassistant.config_entries.ConfigEntries.async_setup", return_value=True):
        yield
