"""System tests for integration entry points."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import Platform

from custom_components.ora import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)


class TestIntegrationSetup:
    """Test integration setup."""

    @pytest.fixture
    def mock_api(self):
        api = MagicMock()
        api.set_access_token = MagicMock()
        api.close = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, mock_api):
        """Test async_setup_entry."""
        mock_hass = MagicMock()
        mock_hass.data = {}
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"
        config_entry.data = {
            "region": "eu",
            "device_id": "device_456",
            "access_token": "token_abc",
            "refresh_token": "refresh_xyz",
            "poll_interval": 60,
        }

        with (
            patch(
                "custom_components.ora.GwmApi",
                return_value=mock_api,
            ),
            patch(
                "custom_components.ora.OraCoordinator",
            ) as MockCoordinator,
        ):
            mock_coordinator = MagicMock()
            MockCoordinator.return_value = mock_coordinator

            result = await async_setup_entry(mock_hass, config_entry)

            assert result is True
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
                config_entry, PLATFORMS
            )

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_api):
        """Test async_unload_entry."""
        mock_hass = MagicMock()
        mock_hass.data = {
            "ora": {
                "test_entry_123": MagicMock(stop=MagicMock()),
            }
        }
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"

        result = await async_unload_entry(mock_hass, config_entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            config_entry, PLATFORMS
        )

    @pytest.mark.asyncio
    async def test_async_unload_entry_cleans_data(self, mock_api):
        """Test async_unload_entry cleans up data."""
        mock_hass = MagicMock()
        coordinator = MagicMock()
        coordinator.stop = MagicMock()
        mock_hass.data = {"ora": {"test_entry_123": coordinator}}
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"

        await async_unload_entry(mock_hass, config_entry)

        assert "test_entry_123" not in mock_hass.data["ora"]

class TestIntegrationPlatforms:
    """Test integration platforms."""

    def test_platforms_defined(self):
        """Test platforms are defined."""
        assert Platform.SENSOR in PLATFORMS
        assert Platform.BINARY_SENSOR in PLATFORMS
        assert Platform.DEVICE_TRACKER in PLATFORMS

    def test_all_platforms_count(self):
        """Test correct number of platforms."""
        assert len(PLATFORMS) == 3
