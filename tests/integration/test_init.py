"""Integration tests for __init__.py — coordinator setup and update listener."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ora import (
    PLATFORMS,
    _async_entry_updated_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.ora.const import DEFAULT_POLL_INTERVAL, DOMAIN
from custom_components.ora.coordinator import OraCoordinator


@pytest.mark.integration
class TestAsyncSetupEntry:
    """Test async_setup_entry."""

    @pytest.mark.asyncio
    async def test_creates_coordinator(self):
        """Test that setup creates a coordinator and stores it."""
        mock_hass = MagicMock()
        mock_hass.data = {}
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_001"
        mock_entry.data = {
            "region": "eu",
            "country": "DE",
            "device_id": "dev_001",
            "access_token": "tok_001",
            "refresh_token": "ref_001",
            "poll_interval": 30,
        }
        mock_entry.options = {}

        with (
            patch("custom_components.ora.GwmApi") as mock_api_cls,
            patch("custom_components.ora.OraCoordinator") as mock_coord_cls,
        ):
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            mock_coord = MagicMock(spec=OraCoordinator)
            mock_coord_cls.return_value = mock_coord

            result = await async_setup_entry(mock_hass, mock_entry)

        assert result is True
        mock_api_cls.assert_called_once_with(region="eu")
        mock_api.set_access_token.assert_called_once_with("tok_001")
        mock_coord_cls.assert_called_once()
        assert mock_hass.data[DOMAIN]["entry_001"] is mock_coord
        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, PLATFORMS
        )

    @pytest.mark.asyncio
    async def test_registers_update_listener(self):
        """Test that setup registers the update listener."""
        mock_hass = MagicMock()
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_002"
        mock_entry.data = {"device_id": "d", "access_token": "t", "refresh_token": "r"}
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()
        mock_entry.add_update_listener = MagicMock()

        with (
            patch("custom_components.ora.GwmApi"),
            patch("custom_components.ora.OraCoordinator"),
        ):
            await async_setup_entry(mock_hass, mock_entry)

        mock_entry.add_update_listener.assert_called_once()
        fn = mock_entry.add_update_listener.call_args[0][0]
        assert fn.__name__ == "_async_entry_updated_listener"
        mock_entry.async_on_unload.assert_called_once()


@pytest.mark.integration
class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unloads_platforms_and_shuts_down_coordinator(self):
        """Test that unload cleans up platforms and coordinator."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "entry_003"
        mock_entry.data = {}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        coordinator = MagicMock()
        coordinator.async_shutdown = AsyncMock()
        mock_hass.data = {DOMAIN: {"entry_003": coordinator}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            mock_entry, PLATFORMS
        )
        coordinator.async_shutdown.assert_awaited_once()
        assert "entry_003" not in mock_hass.data[DOMAIN]


@pytest.mark.integration
class TestAsyncEntryUpdatedListener:
    """Test _async_entry_updated_listener (in-place update, no reload)."""

    @pytest.mark.asyncio
    async def test_updates_access_token(self):
        """Token from entry.data is propagated to coordinator._api."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e1"
        mock_entry.data = {"access_token": "new_token", "refresh_token": "new_ref"}
        mock_entry.options = {}

        coordinator = MagicMock()
        coordinator._api = MagicMock()
        mock_hass.data = {DOMAIN: {"e1": coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        coordinator._api.set_access_token.assert_called_once_with("new_token")
        assert coordinator._refresh_token == "new_ref"

    @pytest.mark.asyncio
    async def test_updates_poll_interval_from_options(self):
        """Poll interval in options is applied to coordinator."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e2"
        mock_entry.data = {}
        mock_entry.options = {"poll_interval": 120}

        coordinator = MagicMock()
        coordinator._api = MagicMock()
        mock_hass.data = {DOMAIN: {"e2": coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        assert coordinator.update_interval == timedelta(seconds=120)

    @pytest.mark.asyncio
    async def test_default_poll_interval_when_options_missing(self):
        """Default poll interval is used when options don't specify."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e3"
        mock_entry.data = {}
        mock_entry.options = {}

        coordinator = MagicMock()
        coordinator._api = MagicMock()
        mock_hass.data = {DOMAIN: {"e3": coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        assert coordinator.update_interval == timedelta(seconds=DEFAULT_POLL_INTERVAL)

    @pytest.mark.asyncio
    async def test_updates_timing_metadata(self):
        """token_issued_at and expires_in are synced from entry.data."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e4"
        mock_entry.data = {
            "access_token": "t",
            "refresh_token": "r",
            "token_issued_at": "2026-01-01T00:00:00+00:00",
            "expires_in": 7200,
        }
        mock_entry.options = {}

        coordinator = MagicMock()
        coordinator._api = MagicMock()
        coordinator._token_issued_at = "old"
        coordinator._expires_in = 0
        mock_hass.data = {DOMAIN: {"e4": coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        assert coordinator._token_issued_at == "2026-01-01T00:00:00+00:00"
        assert coordinator._expires_in == 7200

    @pytest.mark.asyncio
    async def test_keeps_existing_timing_when_entry_has_none(self):
        """Existing timing values are preserved when entry.data lacks them."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e5"
        mock_entry.data = {"access_token": "t", "refresh_token": "r"}
        mock_entry.options = {}

        coordinator = MagicMock()
        coordinator._api = MagicMock()
        coordinator._token_issued_at = "existing_ts"
        coordinator._expires_in = 3600
        mock_hass.data = {DOMAIN: {"e5": coordinator}}

        await _async_entry_updated_listener(mock_hass, mock_entry)

        assert coordinator._token_issued_at == "existing_ts"
        assert coordinator._expires_in == 3600

    @pytest.mark.asyncio
    async def test_noop_when_no_coordinator(self):
        """Listener does nothing when no coordinator exists for the entry."""
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "e6"
        mock_hass.data = {}

        # Should not raise
        await _async_entry_updated_listener(mock_hass, mock_entry)
