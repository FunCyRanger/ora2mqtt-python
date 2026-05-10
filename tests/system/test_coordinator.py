"""System tests for coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ora.api import Vehicle, VehicleStatus, VehicleStatusItem
from custom_components.ora.api.client import GwmApiException
from custom_components.ora.coordinator import OraCoordinator, VehicleData


@pytest.fixture(autouse=True)
def _patch_frame_helper():
    """Prevent DataUpdateCoordinator.__init__ from raising Frame helper error."""
    with patch("homeassistant.helpers.frame.report_usage"):
        yield


class TestOraCoordinator:
    """Test OraCoordinator."""

    @pytest.fixture
    def mock_api(self):
        api = MagicMock()
        api.auth.get_user_info = AsyncMock()
        api.auth.refresh_token = AsyncMock(
            return_value=MagicMock(
                access_token="new_token",
                refresh_token="new_refresh",
            )
        )
        api.vehicles.acquire_vehicles = AsyncMock(
            return_value=[
                Vehicle(
                    vin="LHG12345678901234",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_001",
                )
            ]
        )
        api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="LHG12345678901234",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.520008,
                longitude=13.404954,
                items=[
                    VehicleStatusItem(code=2013021, value="75", unit="%"),
                    VehicleStatusItem(code=2011501, value="250", unit="km"),
                ],
            )
        )
        return api

    @pytest.fixture
    def coordinator(self, mock_api):
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        return OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

    def test_coordinator_initialization(self, coordinator):
        """Test coordinator initialization."""
        assert coordinator._device_id == "device_123"
        assert coordinator._refresh_token == "refresh_token"
        assert coordinator._poll_interval == 60
        assert coordinator.update_interval.total_seconds() == 60

    @pytest.mark.asyncio
    async def test_async_update_data_success(self, coordinator, mock_api):
        """Test successful data update."""
        result = await coordinator._async_update_data()

        assert "LHG12345678901234" in result
        vehicle_data = result["LHG12345678901234"]
        assert isinstance(vehicle_data, VehicleData)
        assert vehicle_data.vehicle.vin == "LHG12345678901234"
        assert vehicle_data.status is not None

    @pytest.mark.asyncio
    async def test_non_570062_api_error_propagates(self, coordinator, mock_api):
        """Non-570062 API error from vehicle fetch propagates through, no refresh."""
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=GwmApiException("500001", "Internal server error")
        )

        with pytest.raises(GwmApiException, match="500001"):
            await coordinator._async_update_data()

        mock_api.auth.refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_update_data_multiple_vehicles(self, coordinator, mock_api):
        """Test data update with multiple vehicles."""
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            return_value=[
                Vehicle(
                    vin="LHG12345678901234",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_001",
                ),
                Vehicle(
                    vin="LHG98765432109876",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_002",
                ),
            ]
        )

        result = await coordinator._async_update_data()

        assert len(result) == 2
        assert "LHG12345678901234" in result
        assert "LHG98765432109876" in result

    @pytest.mark.asyncio
    async def test_async_update_data_partial_failure(self, coordinator, mock_api):
        """Test data update with partial vehicle failure."""
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            return_value=[
                Vehicle(
                    vin="LHG12345678901234",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_001",
                ),
                Vehicle(
                    vin="LHG98765432109876",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_002",
                ),
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            side_effect=[
                Exception("Network error"),
                VehicleStatus(
                    vin="LHG98765432109876",
                    acquisition_time=1704067200000,
                    update_time=1704067200000,
                    device_id="device_002",
                    latitude=52.520008,
                    longitude=13.404954,
                    items=[],
                ),
            ]
        )

        result = await coordinator._async_update_data()

        assert "LHG12345678901234" in result
        assert result["LHG12345678901234"].status is None  # Failed
        assert "LHG98765432109876" in result
        assert result["LHG98765432109876"].status is not None  # Success


class TestOraCoordinatorIntegration:
    """Integration tests for coordinator with HA."""

    @pytest.mark.asyncio
    async def test_coordinator_updates_config_entry_on_570062(self):
        """Test that coordinator updates config entry on 570062 from vehicle API."""
        mock_hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "poll_interval": 60,
        }
        mock_hass.config_entries.async_update_entry = AsyncMock()

        mock_api = MagicMock()
        mock_api.auth.refresh_token = AsyncMock(
            return_value=MagicMock(
                access_token="new_token",
                refresh_token="new_refresh",
            )
        )
        mock_api.set_access_token = MagicMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=[
                GwmApiException("570062", "Access token expired"),
                [
                    Vehicle(
                        vin="LHG12345678901234",
                        brand_name="ORA",
                        app_show_series_name="Funky Cat",
                        vtype="Funky Cat",
                        device_id="device_001",
                    )
                ],
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="LHG12345678901234",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.520008,
                longitude=13.404954,
                items=[],
            )
        )

        coordinator = OraCoordinator(
            hass=mock_hass,
            api=mock_api,
            device_id="device_123",
            refresh_token="old_refresh",
            poll_interval=60,
            entry=config_entry,
        )

        await coordinator._async_update_data()

        mock_hass.config_entries.async_update_entry.assert_called_once()
        call_args = mock_hass.config_entries.async_update_entry.call_args
        updated_data = call_args.kwargs["data"]
        assert updated_data["access_token"] == "new_token"
        assert updated_data["refresh_token"] == "new_refresh"


@pytest.mark.integration
class TestTokenCheckBehavior:
    """Test token validation and refresh behavior in _async_update_data."""

    @pytest.mark.asyncio
    async def test_570062_triggers_refresh_and_succeeds(self):
        """Vehicle API returns 570062 → token refresh → retry succeeds."""
        mock_api = MagicMock()
        mock_api.auth.refresh_token = AsyncMock(
            return_value=MagicMock(
                access_token="new_token",
                refresh_token="new_refresh",
            )
        )
        mock_api.set_access_token = MagicMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=[
                GwmApiException("570062", "Access token expired"),
                [
                    Vehicle(
                        vin="VIN001",
                        brand_name="ORA",
                        app_show_series_name="Funky Cat",
                        vtype="Funky Cat",
                        device_id="device_001",
                    )
                ],
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="VIN001",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.52,
                longitude=13.404,
                items=[VehicleStatusItem(code=2013021, value="75", unit="%")],
            )
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "dev_001",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="dev_001",
            refresh_token="old_refresh",
            poll_interval=60,
            entry=config_entry,
        )

        result = await coordinator._async_update_data()

        assert "VIN001" in result
        mock_api.auth.refresh_token.assert_called_once()
        mock_api.set_access_token.assert_called_once_with("new_token")

    @pytest.mark.asyncio
    async def test_570062_then_refresh_also_570062_raises_auth_failed(self):
        """Vehicle API returns 570062 → refresh also fails with 570062 → auth failed."""
        mock_api = MagicMock()
        mock_api.auth.refresh_token = AsyncMock(
            side_effect=GwmApiException("570062", "Refresh Token has expired")
        )
        mock_api.set_access_token = MagicMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=GwmApiException("570062", "Access token expired")
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "dev_001",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="dev_001",
            refresh_token="old_refresh",
            poll_interval=60,
            entry=config_entry,
        )

        with pytest.raises(Exception, match="refresh token expired"):
            await coordinator._async_update_data()

        mock_api.auth.refresh_token.assert_called_once()


@pytest.mark.integration
class TestRetryLogic:
    """Test retry logic for transient errors.

    Note: These tests require HA test fixtures but fail due to Frame helper issues.
    They document the expected behavior but may not run in all test environments.
    """

    @pytest.mark.asyncio
    async def test_fetch_vehicle_data_retries_on_transient_error(self):
        """Test that fetching vehicle data retries on transient API errors."""
        mock_api = MagicMock()
        mock_api.auth.get_user_info = AsyncMock()
        mock_api.auth.refresh_token = AsyncMock()

        # First call fails with transient error, second succeeds
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=[
                GwmApiException("308024", "Rate limit"),
                [
                    Vehicle(
                        vin="LHG12345678901234",
                        brand_name="ORA",
                        app_show_series_name="Funky Cat",
                        vtype="Funky Cat",
                        device_id="device_001",
                    )
                ],
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="LHG12345678901234",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.520008,
                longitude=13.404954,
                items=[],
            )
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

        # The coordinator should retry and eventually succeed
        result = await coordinator._fetch_vehicle_data_with_retry()

        assert "LHG12345678901234" in result
        assert result["LHG12345678901234"].status is not None

    @pytest.mark.asyncio
    async def test_fetch_vehicle_data_raises_after_max_retries(self):
        """Test that fetching vehicle data raises after max retries exhausted."""
        mock_api = MagicMock()
        mock_api.auth.get_user_info = AsyncMock()
        mock_api.auth.refresh_token = AsyncMock()

        # Always fail with transient error
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=GwmApiException("308024", "Rate limit")
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

        # Should raise after max retries
        with pytest.raises(GwmApiException) as exc_info:
            await coordinator._fetch_vehicle_data_with_retry()

        assert exc_info.value.code == "308024"

    @pytest.mark.asyncio
    async def test_non_570062_api_error_propagates_from_vehicle_fetch(self):
        """Non-570062 error from vehicle API propagates, no refresh."""
        mock_api = MagicMock()
        mock_api.auth.refresh_token = AsyncMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            side_effect=GwmApiException("500001", "Internal server error")
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

        with pytest.raises(GwmApiException, match="500001"):
            await coordinator._async_update_data()

        mock_api.auth.refresh_token.assert_not_called()


class TestFetchVehicleDataWithRetryIsMethod:
    """Regression tests: _fetch_vehicle_data_with_retry must be a bound method.

    Previously this was a module-level function, so self._fetch_vehicle_data_with_retry()
    resolved to the function itself (not a bound method), causing infinite recursion
    when the coordinator polled. This is caught by these tests.
    """

    @pytest.mark.asyncio
    async def test_fetch_vehicle_data_with_retry_is_bound_method(self):
        """Verify _fetch_vehicle_data_with_retry is a bound method on the coordinator."""
        mock_api = MagicMock()
        mock_api.auth.get_user_info = AsyncMock()
        mock_api.auth.refresh_token = AsyncMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            return_value=[
                Vehicle(
                    vin="LHG12345678901234",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_001",
                )
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="LHG12345678901234",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.520008,
                longitude=13.404954,
                items=[],
            )
        )

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

        # Verify it's a bound method, not a plain function
        method = coordinator._fetch_vehicle_data_with_retry
        assert hasattr(method, "__self__"), (
            "_fetch_vehicle_data_with_retry is not a bound method - "
            "it's likely still a module-level function causing infinite recursion"
        )
        assert method.__self__ is coordinator

        # Call it - if this recurses infinitely, the test will hang/timeout
        result = await method()
        assert "LHG12345678901234" in result

    @pytest.mark.asyncio
    async def test_async_update_data_calls_method_not_function(self):
        """Test that _async_update_data calls the bound method.

        This test verifies the full call chain from _async_update_data
        through to _fetch_vehicle_data_with_retry doesn't trigger infinite recursion.
        """
        mock_api = MagicMock()
        mock_api.auth.get_user_info = AsyncMock()
        mock_api.auth.refresh_token = AsyncMock()
        mock_api.vehicles.acquire_vehicles = AsyncMock(
            return_value=[
                Vehicle(
                    vin="VIN123456789ABCDE",
                    brand_name="ORA",
                    app_show_series_name="Funky Cat",
                    vtype="Funky Cat",
                    device_id="device_001",
                )
            ]
        )
        mock_api.vehicles.get_last_status = AsyncMock(
            return_value=VehicleStatus(
                vin="VIN123456789ABCDE",
                acquisition_time=1704067200000,
                update_time=1704067200000,
                device_id="device_001",
                latitude=52.520008,
                longitude=13.404954,
                items=[],
            )
        )

        config_entry = MagicMock()
        config_entry.entry_id = "entry_001"
        config_entry.data = {
            "device_id": "device_123",
            "refresh_token": "refresh_token",
            "poll_interval": 60,
        }
        config_entry.config_entries.async_update_entry = MagicMock()

        coordinator = OraCoordinator(
            hass=MagicMock(),
            api=mock_api,
            device_id="device_123",
            refresh_token="refresh_token",
            poll_interval=60,
            entry=config_entry,
        )

        # Verify _fetch_vehicle_data_with_retry is a bound method
        assert hasattr(coordinator._fetch_vehicle_data_with_retry, "__self__"), (
            "_fetch_vehicle_data_with_retry is not a bound method - "
            "it's likely still a module-level function causing infinite recursion"
        )
        assert coordinator._fetch_vehicle_data_with_retry.__self__ is coordinator

        result = await coordinator._async_update_data()
        assert "VIN123456789ABCDE" in result
