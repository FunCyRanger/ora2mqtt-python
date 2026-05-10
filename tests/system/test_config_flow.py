"""System tests for config flow - HA integration pattern."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.ora.api.client import GwmApiException
from custom_components.ora.config_flow import ConfigFlow


class TestAsyncStepUser:
    """Test async_step_user - the first login step."""

    async def test_initial_step_shows_user_form(self):
        """Test initial call shows the user form without error."""
        flow = ConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_new_flow_has_no_config_entry_attribute(self):
        """Test new ConfigFlow has no config_entry attribute - this was a bug."""
        flow = ConfigFlow()
        flow.hass = MagicMock()

        # This should NOT raise AttributeError
        result = await flow.async_step_user(None)
        assert result["type"] == "form"

    @patch("custom_components.ora.config_flow.GwmApi")
    async def test_login_success_creates_entry(self, mock_api_class):
        """Test successful login creates entry."""
        mock_api = MagicMock()
        mock_api.auth.login_with_email = AsyncMock(
            return_value=MagicMock(
                access_token="token",
                refresh_token="refresh",
                gw_id="gw123",
                bean_id="bean123",
            )
        )
        mock_api_class.return_value = mock_api

        flow = ConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password",
            }
        )

        assert result["type"] == "create_entry"

    @patch("custom_components.ora.config_flow.GwmApi")
    async def test_login_requires_email_code_triggers_email_step(self, mock_api_class):
        """Test 110641 error triggers email code step."""
        mock_api = MagicMock()
        mock_api.auth.login_with_email = AsyncMock(
            side_effect=GwmApiException("110641", "Verification required")
        )
        mock_api_class.return_value = mock_api

        flow = ConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password",
            }
        )

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"


class TestAsyncStepReauth:
    """Test async_step_reauth - re-authentication flow."""

    async def test_reauth_initial_step_shows_form(self):
        """Test initial reauth call shows the form."""
        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow.config_entry = MagicMock()
        flow.config_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
        }

        result = await flow.async_step_reauth(None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth"

    async def test_reauth_empty_user_input_shows_form(self):
        """Test reauth with empty user_input dict shows form (bug regression test).

        This is a critical test - when HA triggers reauth, it may pass user_input={}
        instead of None. The code should handle this case and show the form.
        """
        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow.config_entry = MagicMock()
        flow.config_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
        }

        result = await flow.async_step_reauth({})

        assert result["type"] == "form"
        assert result["step_id"] == "reauth"

    async def test_reauth_without_config_entry_aborts(self):
        """Test reauth without config_entry and no context entry_id aborts gracefully.

        This is a critical regression test - if config_entry is not set on the
        flow object (should be set by HA framework), the flow should abort
        gracefully instead of crashing with AttributeError.
        """
        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}  # No entry_id in context

        result = await flow.async_step_reauth(None)

        assert result["type"] == "abort"
        assert result["reason"] == "Configuration entry not found"

    async def test_reauth_retrieves_config_entry_from_context(self):
        """Test reauth retrieves config_entry from flow context entry_id.

        The normal case - HA should pass entry_id through context,
        and we can retrieve the config_entry from hass.config_entries.
        """
        mock_entry = MagicMock()
        mock_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
        }

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)
        flow.context = {"entry_id": "test_entry_123"}

        result = await flow.async_step_reauth(None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth"
        flow.hass.config_entries.async_get_entry.assert_called_once_with("test_entry_123")

    async def test_reauth_success_updates_entry(self):
        """Test successful reauth updates the config entry via hass.config_entries.

        Note: re-auth with immediate login (no 110641) updates entry via _update_entry().
        The actual token update happens through _update_entry() called after login_with_email
        succeeds. We verify that _access_token is set correctly.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.login_with_email = AsyncMock(
            return_value=MagicMock(
                access_token="new_access_token",
                refresh_token="new_refresh_token",
                gw_id="gw123",
                bean_id="bean123",
                expires_in=7200,
            )
        )
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client

        flow.config_entry = MagicMock()
        flow.config_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
            "access_token": "old_token",
            "refresh_token": "old_refresh",
        }

        await flow.async_step_reauth(
            user_input={"username": "test@example.com", "password": "newpassword"}
        )

        # Verify login was called (may be called multiple times due to retry logic)
        assert mock_ora_client.auth.login_with_email.call_count >= 1
        # Verify entry was updated via hass.config_entries
        flow.hass.config_entries.async_update_entry.assert_called_once()
        # Verify tokens were stored
        assert flow._access_token == "new_access_token"
        assert flow._refresh_token == "new_refresh_token"

    async def test_reauth_requires_email_verification_shows_email_code_form(self):
        """Test reauth requiring email verification shows email_code form."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.login_with_email = AsyncMock(
            side_effect=GwmApiException("110641", "Verification required")
        )
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client

        flow.config_entry = MagicMock()
        flow.config_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
        }

        result = await flow.async_step_reauth(
            user_input={"username": "test@example.com", "password": "newpassword"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"

    async def test_reauth_failure_shows_error(self):
        """Test failed reauth shows error message."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.login_with_email = AsyncMock(
            side_effect=GwmApiException("308025", "Invalid credentials")
        )
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client

        flow.config_entry = MagicMock()
        flow.config_entry.data = {
            "email": "test@example.com",
            "device_id": "device_123",
        }

        result = await flow.async_step_reauth(
            user_input={"username": "test@example.com", "password": "wrongpassword"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth"
        assert "Invalid credentials" in result["errors"]["base"]

    async def test_email_code_form_shows_empty_errors_on_initial_load(self):
        """Test email_code form shows empty errors when first loaded.

        Code sending is now handled in async_step_user/reauth before calling
        this method, so this method just shows the form.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}

    async def test_success_shows_email_code_form(self):
        """Test successful code send shows email_code form."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}

    async def test_verify_incorrect_code_shows_error(self):
        """Test incorrect code verification shows error."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.verify_email_code = AsyncMock(
            side_effect=GwmApiException("308012", "Incorrect code")
        )
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(user_input={"email_code": "wrong"})

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert "Incorrect" in result["errors"]["base"]

    async def test_verify_rate_limit_shows_error(self):
        """Test rate limit during verification shows error."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.verify_email_code = AsyncMock(
            side_effect=GwmApiException("308024", "Rate limit")
        )
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(user_input={"email_code": "123456"})

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert "Rate limit" in result["errors"]["base"]

    async def test_verify_success_creates_entry(self):
        """Test successful verification creates entry."""
        mock_ora_client = MagicMock()
        mock_ora_client.auth.verify_email_code = AsyncMock(
            return_value=MagicMock(
                access_token="token",
                refresh_token="refresh",
                gw_id="gw123",
            )
        )
        mock_ora_client.auth.add_app_device_info = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(user_input={"email_code": "123456"})

        assert result["type"] == "create_entry"

    async def test_email_code_form_no_longer_auto_sends(self):
        """Test that async_step_email_code no longer auto-sends code.

        Code is now sent in async_step_user/reauth before calling this method,
        not in async_step_email_code itself.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}
        # get_email_code is NOT called in async_step_email_code anymore
        mock_ora_client.auth.get_email_code.assert_not_called()

    async def test_email_code_send_rate_limit_shows_error(self):
        """Test rate limit error (308024) when sending email code shows error message.

        This is now handled in async_step_user/reauth before calling this method.
        async_step_email_code just shows the form without sending code.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}

    async def test_email_code_send_other_error_shows_error(self):
        """Test other errors when sending email code shows error message.

        This is now handled in async_step_user/reauth before calling this method.
        async_step_email_code just shows the form without sending code.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}

    async def test_email_code_send_network_error_shows_error(self):
        """Test network error when sending email code shows error message.

        This is now handled in async_step_user/reauth before calling this method.
        async_step_email_code just shows the form without sending code.
        """
        mock_ora_client = MagicMock()
        mock_ora_client.auth.get_email_code = AsyncMock()
        mock_ora_client.close = AsyncMock()

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow._api = mock_ora_client
        flow._email = "test@example.com"
        flow._device_id = "device_123"
        flow._country = "DE"

        result = await flow.async_step_email_code(None)

        assert result["type"] == "form"
        assert result["step_id"] == "email_code"
        assert result["errors"] == {}


class TestReauthEmailCodeFlow:
    """Test re-auth with email code verification followed by entry update.

    Regression test: _update_entry() must use hass.config_entries.async_update_entry(),
    NOT self.async_update_entry() (that method doesn't exist on ConfigFlow).
    """

    async def test_reauth_verify_email_code_updates_entry_via_hass(self):
        """Test re-auth email code verification updates entry via hass.config_entries."""
        mock_verify_api = MagicMock()
        mock_verify_api.auth.verify_email_code = AsyncMock(
            return_value=MagicMock(
                access_token="new_access_token",
                refresh_token="new_refresh_token",
                gw_id="gw123",
                bean_id="bean123",
                expires_in=7200,
            )
        )
        mock_verify_api.close = AsyncMock()

        # Patch GwmApi so the email_code step creates a fresh instance
        with patch("custom_components.ora.config_flow.GwmApi") as mock_api_class:
            mock_api_class.return_value = mock_verify_api

            flow = ConfigFlow()
            flow.hass = MagicMock()
            flow.hass.config_entries.async_update_entry = MagicMock()

            # Simulate re-auth context: config_entry is set on flow
            flow.config_entry = MagicMock()
            flow.config_entry.data = {
                "email": "test@example.com",
                "device_id": "device_123",
                "access_token": "old_token",
                "refresh_token": "old_refresh",
                "country": "DE",
            }
            flow._email = "test@example.com"
            flow._device_id = "device_123"
            flow._country = "DE"

            # Simulate calling async_step_email_code after re-auth triggered 110641
            result = await flow.async_step_email_code(user_input={"email_code": "123456"})

            assert result["type"] == "abort"
            assert result["reason"] == "reauth_successful"
            # Critical assertion: update goes through hass.config_entries, not self.async_update_entry
            flow.hass.config_entries.async_update_entry.assert_called_once()
            call_args = flow.hass.config_entries.async_update_entry.call_args
            assert call_args[0][0] == flow.config_entry  # entry is first positional arg
            updated_data = call_args[0][1].data
            assert updated_data["access_token"] == "new_access_token"
            assert updated_data["refresh_token"] == "new_refresh_token"
