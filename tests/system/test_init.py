"""System tests for __init__.py integration setup and reload flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ora import (
    _async_entry_updated_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.ora.coordinator import OraCoordinator


class TestAsyncSetupEntry:
    """Test async_setup_entry."""

    async def test_setup_creates_coordinator_and_stores_it(self):
        """Test that setup creates a coordinator and stores it in hass.data."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_123"
        mock_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
            "access_token": "token123",
            "refresh_token": "refresh123",
            "region": "eu",
            "country": "DE",
            "poll_interval": 60,
        }
        mock_entry.options = {}

        with patch("custom_components.ora.GwmApi") as mock_api_class:
            mock_api = MagicMock()
            mock_api.set_access_token = MagicMock()
            mock_api_class.return_value = mock_api

            result = await async_setup_entry(mock_hass, mock_entry)

        assert result is True
        domain_data = mock_hass.data.setdefault.call_args[0][0]
        assert "ora" in domain_data
        assert "test_entry_123" in domain_data["ora"]
        coordinator = domain_data["ora"]["test_entry_123"]
        assert isinstance(coordinator, OraCoordinator)
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once()

    async def test_setup_registers_update_listener(self):
        """Test that setup registers an update listener on the entry."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_456"
        mock_entry.data = {
            "device_id": "device_456",
            "access_token": "token456",
            "refresh_token": "refresh456",
        }
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()
        mock_entry.add_update_listener = MagicMock()

        with patch("custom_components.ora.GwmApi") as mock_api_class:
            mock_api = MagicMock()
            mock_api.set_access_token = MagicMock()
            mock_api_class.return_value = mock_api

            await async_setup_entry(mock_hass, mock_entry)

        mock_entry.add_update_listener.assert_called_once()
        # The listener should be _async_entry_updated_listener
        listener_fn = mock_entry.add_update_listener.call_args[0][0]
        assert listener_fn.__name__ == "_async_entry_updated_listener"


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    async def test_unload_removes_coordinator_and_unloads_platforms(self):
        """Test that unload removes coordinator and unloads platforms."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "unload_entry_789"
        mock_entry.data = {}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Pre-populate domain data with a coordinator that has async_shutdown
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()
        mock_hass.data = {"ora": {"unload_entry_789": mock_coordinator}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()
        mock_coordinator.async_shutdown.assert_awaited_once()
        assert "unload_entry_789" not in mock_hass.data["ora"]


class TestAsyncEntryUpdatedListener:
    """Test the update listener that handles re-auth and options changes.

    The listener now updates the coordinator in-place instead of doing a full reload.
    """

    async def test_listener_updates_coordinator_tokens(self):
        """Test that the update listener updates coordinator tokens in-place."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "update_test_001"
        mock_entry.data = {
            "device_id": "device_update",
            "access_token": "new_token",
            "refresh_token": "new_refresh",
        }
        mock_entry.options = {}

        mock_coordinator = MagicMock()
        mock_coordinator._api = MagicMock()
        mock_hass.data = {"ora": {"update_test_001": mock_coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        mock_coordinator._api.set_access_token.assert_called_once_with("new_token")
        assert mock_coordinator._refresh_token == "new_refresh"

    async def test_listener_updates_poll_interval(self):
        """Test that the update listener picks up poll interval from options."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "interval_test"
        mock_entry.data = {}
        mock_entry.options = {"poll_interval": 120}

        mock_coordinator = MagicMock()
        mock_coordinator._api = MagicMock()
        mock_hass.data = {"ora": {"interval_test": mock_coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        assert mock_coordinator.update_interval == timedelta(seconds=120)

    async def test_listener_noop_when_no_coordinator(self):
        """Test that the listener does nothing when there's no coordinator."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "no_coord_test"
        mock_hass.data = {}

        await _async_entry_updated_listener(mock_hass, mock_entry)
