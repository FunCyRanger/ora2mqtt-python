"""End-to-end tests for config flow using HA flow system and HTTP-level mocking."""

from aioresponses import aioresponses
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.ora.const import (
    CONF_ACCOUNT_ACCESS_TOKEN,
    CONF_ACCOUNT_BEAN_ID,
    CONF_ACCOUNT_DEVICE_ID,
    CONF_ACCOUNT_EMAIL,
    CONF_ACCOUNT_GWID,
    CONF_ACCOUNT_REFRESH_TOKEN,
    CONF_API_REGION,
    DOMAIN,
)

H5_BASE_URL = "https://eu-h5-gateway.gwmcloud.com/app-api/api/v1.0/"


def _login_success_response(
    access_token="test_token",
    refresh_token="test_refresh",
    gw_id="gw123",
    bean_id="bean123",
    code="000000",
):
    return {
        "code": code,
        "description": "Success",
        "data": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": 7200,
            "userId": "user123",
            "gwId": gw_id,
            "beanId": bean_id,
        },
    }


def _error_response(code, description):
    return {"code": code, "description": description}


class TestConfigFlowE2E:
    """End-to-end tests for the full config flow through HA's flow system."""

    async def test_happy_path_direct_login(self, hass):
        """Test successful login without email verification."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_login_success_response(),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            assert result["type"] == "form"
            assert result["step_id"] == "user"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "create_entry"
            assert result["title"] == "ORA (test)"
            assert result["data"][CONF_ACCOUNT_EMAIL] == "test@example.com"
            assert result["data"][CONF_ACCOUNT_ACCESS_TOKEN] == "test_token"
            assert result["data"][CONF_ACCOUNT_REFRESH_TOKEN] == "test_refresh"
            assert result["data"][CONF_ACCOUNT_GWID] == "gw123"
            assert result["data"][CONF_ACCOUNT_BEAN_ID] == "bean123"
            assert result["data"][CONF_API_REGION] == "eu"

    async def test_full_flow_with_email_verification(self, hass):
        """Test full flow: login requires email code → send code → verify → entry."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_login_success_response(code="000000"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/loginWithSMS",
                payload=_login_success_response(
                    access_token="verified_token",
                    refresh_token="verified_refresh",
                    gw_id="gw456",
                    bean_id="bean456",
                ),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "email_code"
            assert result["errors"] == {}

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"email_code": "123456"},
            )

            assert result["type"] == "create_entry"
            assert result["title"] == "ORA (test)"
            assert result["data"][CONF_ACCOUNT_EMAIL] == "test@example.com"
            assert result["data"][CONF_ACCOUNT_ACCESS_TOKEN] == "verified_token"
            assert result["data"][CONF_ACCOUNT_DEVICE_ID] is not None

    async def test_email_code_rate_limit_308024(self, hass):
        """Test rate limit during email code send shows email_code form with message."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_error_response("308024", "Rate limit exceeded"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "email_code"
            assert "Rate limit" in result["errors"]["base"]

    async def test_email_code_other_error_returns_to_user(self, hass):
        """Test other GwmApiException during email code send returns to user step."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_error_response("308025", "Some other error"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "user"
            assert result["errors"]["base"] == "Error 308025: Some other error"

    async def test_email_code_generic_exception_returns_to_user(self, hass):
        """Test generic exception during email code send returns to user step."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                exception=Exception("Network error"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "user"
            assert result["errors"]["base"] == "Network error"

    async def test_verify_incorrect_code_shows_error(self, hass):
        """Test incorrect verification code shows error on email_code form."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_login_success_response(),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/loginWithSMS",
                payload=_error_response("308012", "Incorrect code"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["step_id"] == "email_code"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"email_code": "wrong"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "email_code"
            assert "Incorrect" in result["errors"]["base"]

    async def test_verify_rate_limit_shows_error(self, hass):
        """Test rate limit during verification shows error on email_code form."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_login_success_response(),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/loginWithSMS",
                payload=_error_response("308024", "Rate limit exceeded"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"email_code": "123456"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "email_code"
            assert "Rate limit" in result["errors"]["base"]

    async def test_login_generic_exception_returns_to_user(self, hass):
        """Test generic exception during initial login returns to user step."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                exception=Exception("Connection refused"),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "user"
            assert result["errors"]["base"] == "Connection refused"

    async def test_recovery_from_error_to_success(self, hass):
        """Test recovering from an error and completing the flow successfully."""
        with aioresponses() as m:
            m.post(
                f"{H5_BASE_URL}userAuth/loginAccount",
                payload=_error_response("110641", "Email verification required"),
                repeat=True,
            )
            m.post(
                f"{H5_BASE_URL}userAuth/getSMSCode",
                payload=_login_success_response(),
            )
            m.post(
                f"{H5_BASE_URL}userAuth/loginWithSMS",
                payload=_login_success_response(
                    access_token="recovered_token",
                    refresh_token="recovered_refresh",
                    gw_id="gw789",
                    bean_id="bean789",
                ),
            )

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"},
            )

            assert result["type"] == "form"
            assert result["step_id"] == "email_code"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"email_code": "123456"},
            )

            assert result["type"] == "create_entry"
            assert result["data"][CONF_ACCOUNT_ACCESS_TOKEN] == "recovered_token"
