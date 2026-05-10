"""Data coordinator for GWM ORA."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GwmApi, RefreshTokenResponse, Vehicle, VehicleStatus
from .api.client import GwmApiException
from .const import (
    CONF_ACCOUNT_ACCESS_TOKEN,
    CONF_ACCOUNT_EXPIRES_IN,
    CONF_ACCOUNT_REFRESH_TOKEN,
    CONF_ACCOUNT_TOKEN_ISSUED_AT,
    DEFAULT_POLL_INTERVAL,
)
from .privacy import mask_privacy_string

_LOGGER = logging.getLogger(__name__)

# Transient errors that should trigger retry with backoff
TRANSIENT_ERRORS = {"308024"}  # Rate limit only
RETRY_BASE_DELAY = 10  # Base delay in seconds
RETRY_MAX_DELAY = 120  # Max delay in seconds (2 minutes, > poll interval)
RETRY_MAX_ATTEMPTS = 3
TOKEN_REFRESH_BUFFER = 300  # Refresh token 5 minutes before expiry


@dataclass
class VehicleData:
    """Vehicle data for coordinator."""

    vehicle: Vehicle
    status: VehicleStatus | None
    last_update: datetime | None


class OraCoordinator(DataUpdateCoordinator[dict[str, VehicleData]]):
    """Coordinator for fetching vehicle data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: GwmApi,
        device_id: str,
        refresh_token: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        entry: ConfigEntry | None = None,
        token_issued_at: str | None = None,
        expires_in: int | None = None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="GWM ORA",
            update_interval=timedelta(seconds=poll_interval),
        )
        _LOGGER.info(
            "ORA Coordinator: created for entry=%s poll_interval=%s token_issued_at=%s expires_in=%s",
            entry.entry_id if entry else "none",
            poll_interval,
            token_issued_at,
            expires_in,
        )
        self._api = api
        self._device_id = device_id
        self._refresh_token = refresh_token
        self._poll_interval = poll_interval
        self._entry = entry
        self._token_issued_at = token_issued_at
        self._expires_in = expires_in

    async def _do_token_refresh(self) -> RefreshTokenResponse:
        """Refresh access token and update config entry.

        Returns the refresh response.
        Raises GwmApiException or other exceptions for the caller to handle.
        """
        response = await self._api.auth.refresh_token(
            device_id=self._device_id,
            access_token=self._api.access_token or "",
            refresh_token=self._refresh_token,
        )
        self._refresh_token = response.refresh_token
        self._api.set_access_token(response.access_token)

        if self._entry:
            self._token_issued_at = datetime.now(timezone.utc).isoformat()
            self._expires_in = response.expires_in
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    CONF_ACCOUNT_ACCESS_TOKEN: response.access_token,
                    CONF_ACCOUNT_REFRESH_TOKEN: response.refresh_token,
                    CONF_ACCOUNT_TOKEN_ISSUED_AT: self._token_issued_at,
                    CONF_ACCOUNT_EXPIRES_IN: self._expires_in,
                },
            )
        _LOGGER.info("Token refresh successful")
        return response

    async def _proactive_token_refresh(self) -> None:
        """Proactively refresh token before it expires."""
        if not self._token_issued_at or not self._expires_in:
            _LOGGER.debug("No token timing info available, skipping proactive refresh")
            return

        if self._expires_in <= 0:
            _LOGGER.debug("Invalid expires_in (%s), skipping proactive refresh", self._expires_in)
            return

        try:
            issued_at = datetime.fromisoformat(self._token_issued_at)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid token_issued_at format, skipping proactive refresh")
            return

        expiry_time = issued_at + timedelta(seconds=self._expires_in)
        time_until_expiry = (expiry_time - datetime.now(timezone.utc)).total_seconds()

        _LOGGER.debug(
            "Token expires in %d seconds, refresh buffer is %d seconds",
            time_until_expiry,
            TOKEN_REFRESH_BUFFER,
        )

        if 0 < time_until_expiry < TOKEN_REFRESH_BUFFER:
            _LOGGER.info(
                "Proactively refreshing token (expires in %d seconds)",
                time_until_expiry,
            )
            try:
                await self._do_token_refresh()
            except GwmApiException as e:
                _LOGGER.warning("Proactive token refresh failed: %s", e)

    async def _async_update_data(self) -> dict[str, VehicleData]:
        """Fetch vehicle data."""
        _LOGGER.info(
            "ORA: _async_update_data called, token_issued_at=%s expires_in=%s",
            self._token_issued_at,
            self._expires_in,
        )
        await self._proactive_token_refresh()

        try:
            return await self._fetch_vehicle_data_with_retry()
        except GwmApiException as e:
            if e.code not in ("570062", "550004"):
                raise
            _LOGGER.info("Vehicle API returned %s, refreshing token...", e.code)
            try:
                await self._do_token_refresh()
            except GwmApiException as refresh_e:
                if refresh_e.code in ("570062", "550004"):
                    raise ConfigEntryAuthFailed(
                        f"GWM ORA refresh token expired. Please reconfigure: {refresh_e.message}"
                    ) from refresh_e
                _LOGGER.warning("Token refresh failed with transient error: %s", refresh_e)
                raise UpdateFailed(f"Token refresh failed: {refresh_e}") from refresh_e
            except Exception as refresh_e:
                _LOGGER.warning("Token refresh failed: %s", refresh_e)
                raise UpdateFailed(f"Token refresh failed: {refresh_e}") from refresh_e

            _LOGGER.info("Token refreshed, retrying vehicle data fetch")
            return await self._fetch_vehicle_data_with_retry()

    async def _fetch_vehicle_data_with_retry(self) -> dict[str, VehicleData]:
        """Fetch vehicle data with retry for transient errors."""
        _LOGGER.info("ORA: _fetch_vehicle_data_with_retry called as bound method (no recursion)")
        last_error = None

        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                # Get vehicles
                vehicles = await self._api.vehicles.acquire_vehicles()
                result = {}

                for vehicle in vehicles:
                    try:
                        status = await self._api.vehicles.get_last_status(vehicle.vin)
                        result[vehicle.vin] = VehicleData(
                            vehicle=vehicle, status=status, last_update=datetime.now()
                        )
                    except Exception as e:
                        _LOGGER.warning("Failed to get status for %s: %s", mask_privacy_string(vehicle.vin), e)
                        result[vehicle.vin] = VehicleData(
                            vehicle=vehicle, status=None, last_update=None
                        )

                return result

            except GwmApiException as e:
                last_error = e
                if e.code in TRANSIENT_ERRORS:
                    delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                    _LOGGER.warning(
                        "Transient error %s: %s, retrying in %ds (attempt %d/%d)",
                        e.code,
                        e.message,
                        delay,
                        attempt + 1,
                        RETRY_MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                else:
                    _LOGGER.error("Non-transient API error: %s", e)
                    raise
            except Exception as e:
                last_error = e
                delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
                _LOGGER.warning(
                    "Error fetching vehicle data: %s, retrying in %ds (attempt %d/%d)",
                    e,
                    delay,
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                    exc_info=True,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        _LOGGER.error("All retry attempts exhausted for fetching vehicle data")
        raise last_error or Exception("Failed to fetch vehicle data after retries")
