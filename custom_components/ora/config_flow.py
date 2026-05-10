"""Config flow for GWM ORA integration."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


def _get_stable_device_id(hass: HomeAssistant, entry_id: str | None = None) -> str:
    """Generate a stable device ID for this HA instance.

    Uses a deterministic UUID based on the HA config directory path.
    This ensures the same HA instance always gets the same device_id,
    which is important for email verification and token management.

    Args:
        hass: Home Assistant instance
        entry_id: Optional entry_id to include in the hash for additional uniqueness

    Returns:
        Stable device ID string
    """
    # Create a deterministic UUID from the HA config path
    # This ensures same HA instance = same device_id
    namespace = uuid.NAMESPACE_DNS
    name = hass.config.path()
    if entry_id:
        name = f"{name}:{entry_id}"
    return str(uuid.uuid5(namespace, name))


from .api import GwmApi
from .api.client import GwmApiException
from .const import (
    CONF_ACCOUNT_ACCESS_TOKEN,
    CONF_ACCOUNT_BEAN_ID,
    CONF_ACCOUNT_COUNTRY,
    CONF_ACCOUNT_DEVICE_ID,
    CONF_ACCOUNT_EMAIL,
    CONF_ACCOUNT_EXPIRES_IN,
    CONF_ACCOUNT_GWID,
    CONF_ACCOUNT_REFRESH_TOKEN,
    CONF_ACCOUNT_TOKEN_ISSUED_AT,
    CONF_API_REGION,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .privacy import mask_privacy_string, sanitize_for_logging

_LOGGER = logging.getLogger(__name__)

# Transient errors that should trigger retry with backoff
TRANSIENT_ERRORS = {"308024"}  # Rate limit only (550002 is permanent during re-auth)
RETRY_BASE_DELAY = 2  # Base delay in seconds for config flow
RETRY_MAX_ATTEMPTS = 3


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GWM ORA."""

    VERSION = 1

    def __init__(self):
        self._api: GwmApi | None = None
        self._email: str = ""
        self._password: str = ""
        self._device_id: str = ""
        self._country: str = "DE"
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._gw_id: str = ""
        self._bean_id: str = ""

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_reauth(self, user_input=None):
        """Re-authenticate when tokens expire."""
        _LOGGER.info("ORA: async_step_reauth called, user_input=%s", sanitize_for_logging(user_input))
        # Try to get config_entry - it might not be set by HA framework
        # We can get it from the flow context using entry_id
        if not hasattr(self, "config_entry") or not self.config_entry:
            entry_id = self.context.get("entry_id")
            if entry_id:
                self.config_entry = self.hass.config_entries.async_get_entry(entry_id)
                _LOGGER.info("Retrieved config_entry from context for entry: %s", entry_id)

        # If still not available, abort gracefully
        if not hasattr(self, "config_entry") or not self.config_entry:
            _LOGGER.error(
                "Re-auth triggered but config_entry is not available and could not be retrieved from context"
            )
            return self.async_abort(reason="Configuration entry not found")

        if not user_input or CONF_USERNAME not in user_input:
            # Get existing email and country from config entry
            self._email = self.config_entry.data.get(CONF_ACCOUNT_EMAIL, "")
            self._country = self.config_entry.data.get(CONF_ACCOUNT_COUNTRY, "DE")
            return self.async_show_form(
                step_id="reauth",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                errors={},
                description_placeholders={"email": self._email},
            )

        self._email = user_input.get(CONF_USERNAME, self._email)
        self._password = user_input.get(CONF_PASSWORD, "")
        self._request_new_code = user_input.get("request_new_code", True)
        self._device_id = self.config_entry.data.get(CONF_ACCOUNT_DEVICE_ID, "")

        _LOGGER.info(
            "Re-authenticating with email: %s, device_id: %s",
            mask_privacy_string(self._email),
            mask_privacy_string(self._device_id),
        )

        if not self._api:
            self._api = GwmApi()

        # Retry logic for transient errors
        last_error = None
        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                response = await self._api.auth.login_with_email(
                    email=self._email,
                    password=self._password,
                    device_id=self._device_id,
                    country=self._country,
                )
                _LOGGER.info("ORA reauth: loginAccount success, expires_in=%s", response.expires_in)
                await self._api.close()
                return self._update_entry(response)

            except GwmApiException as e:
                last_error = e
                error_msg = str(e)

                # Check for email verification required
                if "110641" in error_msg:
                    _LOGGER.info("110641 error during re-auth - showing email code form")
                    code_send_error = None
                    # Send new code if requested (checkbox is ON by default)
                    if self._request_new_code:
                        try:
                            _LOGGER.info("Sending email verification code to: %s", mask_privacy_string(self._email))
                            # Create a fresh API instance since we may have closed the original
                            email_api = GwmApi()
                            await email_api.auth.get_email_code(self._email)
                            await email_api.close()
                            _LOGGER.info("Email verification code sent successfully")
                        except Exception as code_error:
                            code_send_error = str(code_error)
                            _LOGGER.error(
                                "Failed to send email verification code: %s", code_send_error
                            )
                    await self._api.close()
                    # Store code send error for display in email form
                    self._code_send_error = code_send_error
                    return await self.async_step_email_code()

                # Retry on transient errors
                if e.code in TRANSIENT_ERRORS:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    _LOGGER.warning(
                        "Transient error %s during re-auth: %s, retrying in %ds (attempt %d/%d)",
                        e.code,
                        e.message,
                        delay,
                        attempt + 1,
                        RETRY_MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                    # Continue to next retry
                    continue

                # Non-retryable error
                _LOGGER.error("Non-transient error during re-auth: %s", error_msg)
                await self._api.close()
                errors = {"base": error_msg}
                return self.async_show_form(
                    step_id="reauth",
                    data_schema=STEP_REAUTH_DATA_SCHEMA,
                    errors=errors,
                    description_placeholders={"email": self._email},
                )

            except Exception as e:
                last_error = e
                error_msg = str(e)
                # Retry on generic exceptions
                delay = RETRY_BASE_DELAY * (2**attempt)
                _LOGGER.warning(
                    "Error during re-auth: %s, retrying in %ds (attempt %d/%d)",
                    error_msg,
                    delay,
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        _LOGGER.error("All retry attempts exhausted for re-auth")
        await self._api.close()
        error_message = "Login failed after multiple attempts. The server may be busy. Please try again later, or use Options flow to re-authenticate manually."
        if last_error:
            error_message = f"{error_message} Last error: {last_error}"
        errors = {"base": error_message}
        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    async def async_step_user(self, user_input):
        """Step 1: Enter email and password."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={},
            )

        self._email = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._request_new_code = user_input.get("request_new_code", True)

        # Use existing device_id from config_entry (re-auth case) or generate stable one
        if (
            hasattr(self, "config_entry")
            and self.config_entry
            and self.config_entry.data.get(CONF_ACCOUNT_DEVICE_ID)
        ):
            self._device_id = self.config_entry.data[CONF_ACCOUNT_DEVICE_ID]
            _LOGGER.info("Using existing device_id from config: %s", mask_privacy_string(self._device_id))
        else:
            # Generate stable device_id from HA config path
            self._device_id = _get_stable_device_id(self.hass)
            _LOGGER.info("Generated stable device_id: %s", mask_privacy_string(self._device_id))

        self._api = GwmApi()

        _LOGGER.info("Attempting login with email: %s, device_id: %s", mask_privacy_string(self._email), mask_privacy_string(self._device_id))

        try:
            response = await self._api.auth.login_with_email(
                email=self._email,
                password=self._password,
                device_id=self._device_id,
                country=self._country,
            )
            _LOGGER.info("Login successful, creating entry")
            await self._api.close()
            return self._create_entry(response)
        except Exception as e:
            error_msg = str(e)
            _LOGGER.error("Login failed with error: %s", error_msg)

            await self._api.close()

            if "110641" in error_msg:
                _LOGGER.info("110641 error - showing email code form")
                code_send_error = None
                # Send new code if requested (checkbox is ON by default)
                if self._request_new_code:
                    try:
                        _LOGGER.info("Sending email verification code to: %s", mask_privacy_string(self._email))
                        # Create a fresh API instance since we closed the original
                        email_api = GwmApi()
                        await email_api.auth.get_email_code(self._email)
                        await email_api.close()
                        _LOGGER.info("Email verification code sent successfully")
                    except Exception as code_error:
                        code_send_error = str(code_error)
                        _LOGGER.error("Failed to send email verification code: %s", code_send_error)
                # Store code send error for display in email form
                self._code_send_error = code_send_error
                return await self.async_step_email_code()

            _LOGGER.error("Non-110641 error: %s", error_msg)
            errors = {"base": error_msg}

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_email_code(self, user_input=None):
        """Step 2: Enter email verification code."""
        _LOGGER.info("ORA: async_step_email_code called, user_input=%s", sanitize_for_logging(user_input))
        is_reauth = hasattr(self, "config_entry") and self.config_entry
        _LOGGER.info("ORA: email_code step, is_reauth=%s", is_reauth)

        if user_input is None:
            # Code was already sent (or not) before calling this method
            # No need to auto-send here
            errors = {}
            # Check if there was an error sending the code (e.g., rate limit 308024)
            if hasattr(self, "_code_send_error") and self._code_send_error:
                if "308024" in self._code_send_error:
                    errors["base"] = (
                        "Too many verification codes requested. Please wait a few minutes, or enter a code you received earlier (e.g., from your email app)."
                    )
                else:
                    errors["base"] = f"Failed to send verification code: {self._code_send_error}"
                # Clear the error after displaying
                self._code_send_error = None

            return self.async_show_form(
                step_id="email_code",
                data_schema=STEP_EMAIL_CODE_SCHEMA,
                errors=errors,
            )

        email_code = user_input.get("email_code", "")
        if not email_code:
            return self.async_show_form(
                step_id="email_code",
                data_schema=STEP_EMAIL_CODE_SCHEMA,
                errors={"base": "Please enter the verification code."},
            )

        errors = {}

        try:
            # Create a fresh API instance since the original was closed
            verify_api = GwmApi()
            try:
                _LOGGER.info("ORA: verifying email code for %s", mask_privacy_string(self._email))
                response = await verify_api.auth.verify_email_code(
                    email=self._email,
                    email_code=email_code,
                    device_id=self._device_id,
                    country=self._country,
                )
                _LOGGER.info(
                    "ORA reauth: verify_email_code success, expires_in=%s", response.expires_in
                )
            finally:
                await verify_api.close()

            # Use _update_entry for reauth, _create_entry for new login
            if is_reauth:
                return self._update_entry(response)
            else:
                return self._create_entry(response)
        except Exception as e:
            error_msg = str(e)
            if e.code == "308011":
                errors["base"] = "Incorrect verification code."
            elif "110641" in error_msg:
                errors["base"] = "Incorrect verification code."
            else:
                errors["base"] = error_msg

        return self.async_show_form(
            step_id="email_code",
            data_schema=STEP_EMAIL_CODE_SCHEMA,
            errors=errors,
        )

    def _create_entry(self, response) -> config_entries.ConfigEntry:
        """Create the HA config entry."""
        self._access_token = response.access_token
        self._refresh_token = response.refresh_token
        self._gw_id = response.gw_id
        self._bean_id = response.bean_id
        token_issued_at = datetime.now(timezone.utc).isoformat()
        expires_in = response.expires_in

        return self.async_create_entry(
            title=f"ORA ({self._email.split('@')[0]})",
            data={
                CONF_ACCOUNT_EMAIL: self._email,
                CONF_ACCOUNT_DEVICE_ID: self._device_id,
                CONF_ACCOUNT_ACCESS_TOKEN: self._access_token,
                CONF_ACCOUNT_REFRESH_TOKEN: self._refresh_token,
                CONF_ACCOUNT_GWID: self._gw_id,
                CONF_ACCOUNT_BEAN_ID: self._bean_id,
                CONF_ACCOUNT_TOKEN_ISSUED_AT: token_issued_at,
                CONF_ACCOUNT_EXPIRES_IN: expires_in,
                CONF_ACCOUNT_COUNTRY: self._country,
                CONF_API_REGION: "eu",
                "poll_interval": DEFAULT_POLL_INTERVAL,
            },
        )

    def _update_entry(self, response) -> config_entries.ConfigEntry:
        """Update existing config entry after re-auth."""
        _LOGGER.info("ORA reauth: updating config entry with new tokens")
        self._access_token = response.access_token
        self._refresh_token = response.refresh_token
        self._gw_id = response.gw_id
        self._bean_id = response.bean_id
        token_issued_at = datetime.now(timezone.utc).isoformat()
        expires_in = response.expires_in
        _LOGGER.info(
            "ORA reauth: saving token_issued_at=%s expires_in=%s", token_issued_at, expires_in
        )

        # Update entry data before the abort (which fires the update listener)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_ACCOUNT_EMAIL: self._email,
                CONF_ACCOUNT_DEVICE_ID: self._device_id,
                CONF_ACCOUNT_ACCESS_TOKEN: self._access_token,
                CONF_ACCOUNT_REFRESH_TOKEN: self._refresh_token,
                CONF_ACCOUNT_GWID: self._gw_id,
                CONF_ACCOUNT_BEAN_ID: self._bean_id,
                CONF_ACCOUNT_TOKEN_ISSUED_AT: token_issued_at,
                CONF_ACCOUNT_EXPIRES_IN: expires_in,
                CONF_ACCOUNT_COUNTRY: self._country,
            },
        )
        _LOGGER.info("ORA reauth: entry updated, calling async_abort")

        return self.async_abort(reason="reauth_successful")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for GWM ORA."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            if user_input.get("reauth"):
                return await self.async_step_user(None)
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        poll_interval = options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

        schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=poll_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=300)
                ),
                vol.Optional("reauth", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "description": "Re-authenticate if your refresh token has expired"
            },
        )


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("request_new_code", default=True): bool,
    }
)

STEP_EMAIL_CODE_SCHEMA = vol.Schema(
    {
        vol.Required("email_code"): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("request_new_code", default=True): bool,
    }
)
