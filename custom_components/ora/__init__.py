"""GWM ORA integration for Home Assistant."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import GwmApi
from .const import (
    CONF_ACCOUNT_ACCESS_TOKEN,
    CONF_ACCOUNT_COUNTRY,
    CONF_ACCOUNT_DEVICE_ID,
    CONF_ACCOUNT_EXPIRES_IN,
    CONF_ACCOUNT_REFRESH_TOKEN,
    CONF_ACCOUNT_TOKEN_ISSUED_AT,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import OraCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GWM ORA from a config entry."""
    logging.getLogger("custom_components.ora").setLevel(logging.INFO)
    data = entry.data

    api = GwmApi(region=data.get("region", "eu"))
    api.country = data.get(CONF_ACCOUNT_COUNTRY, "DE")
    api.set_access_token(data.get(CONF_ACCOUNT_ACCESS_TOKEN))

    # Read poll interval from options, fallback to data, then default
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    # Create coordinator
    coordinator = OraCoordinator(
        hass=hass,
        api=api,
        device_id=data[CONF_ACCOUNT_DEVICE_ID],
        refresh_token=data[CONF_ACCOUNT_REFRESH_TOKEN],
        poll_interval=poll_interval,
        entry=entry,
        token_issued_at=data.get(CONF_ACCOUNT_TOKEN_ISSUED_AT),
        expires_in=data.get(CONF_ACCOUNT_EXPIRES_IN),
    )

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("ORA: platforms set up for entry %s", entry.entry_id)

    # Reload on options update
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated_listener))

    return True


async def _async_entry_updated_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update coordinator in-place when entry is updated (re-auth or options)."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not coordinator:
        return

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator.update_interval = timedelta(seconds=poll_interval)

    coordinator._api.set_access_token(entry.data.get(CONF_ACCOUNT_ACCESS_TOKEN))
    coordinator._refresh_token = entry.data.get(
        CONF_ACCOUNT_REFRESH_TOKEN, coordinator._refresh_token
    )
    coordinator._token_issued_at = entry.data.get(
        CONF_ACCOUNT_TOKEN_ISSUED_AT, coordinator._token_issued_at
    )
    coordinator._expires_in = entry.data.get(CONF_ACCOUNT_EXPIRES_IN, coordinator._expires_in)

    _LOGGER.info(
        "ORA: coordinator token timing updated: issued_at=%s expires_in=%s",
        coordinator._token_issued_at,
        coordinator._expires_in,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("ORA: unloading entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        old_coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if old_coordinator:
            await old_coordinator.async_shutdown()
            _LOGGER.info("ORA: coordinator shutdown for entry %s", entry.entry_id)

    return unload_ok
