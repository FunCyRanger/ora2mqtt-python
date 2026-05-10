"""Integration tests for authentication client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ora.api.auth import GwmAuthClient, LoginResponse, RefreshTokenResponse
from tests.fixtures.api_responses import (
    LOGIN_SUCCESS_RESPONSE,
    REFRESH_TOKEN_RESPONSE,
)


class TestGwmAuthClient:
    """Test GwmAuthClient."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.post = AsyncMock(return_value={"code": "000000", "data": {}})
        return client

    @pytest.fixture
    def auth_client(self, mock_client):
        return GwmAuthClient(mock_client)

    @pytest.mark.asyncio
    async def test_get_sms_code(self, auth_client, mock_client):
        """Test getting SMS code."""
        mock_client.post.return_value = {"code": "000000"}

        await auth_client.get_sms_code("+491234567890")

        mock_client.post.assert_called_once_with(
            "userAuth/getSMSCode",
            {
                "phone": "+491234567890",
                "countryCode": "49",
                "captchaCode": "",
                "captchaId": "",
            },
            include_token=False,
        )

    @pytest.mark.asyncio
    async def test_get_sms_code_custom_country(self, auth_client, mock_client):
        """Test getting SMS code with custom country code."""
        mock_client.post.return_value = {"code": "000000"}

        await auth_client.get_sms_code("+441234567890", country_code="44")

        call_args = mock_client.post.call_args
        assert call_args.kwargs["data"]["countryCode"] == "44"

    @pytest.mark.asyncio
    async def test_login_with_sms(self, auth_client, mock_client):
        """Test login with SMS code."""
        mock_client.post.return_value = LOGIN_SUCCESS_RESPONSE

        result = await auth_client.login_with_sms("+491234567890", "123456")

        assert isinstance(result, LoginResponse)
        assert result.access_token == "test_access_token_12345"
        assert result.refresh_token == "test_refresh_token_67890"
        assert result.expires_in == 7200
        assert result.user_id == "user_123456"

    @pytest.mark.asyncio
    async def test_login_with_sms_custom_country(self, auth_client, mock_client):
        """Test login with SMS code with custom country."""
        mock_client.post.return_value = LOGIN_SUCCESS_RESPONSE

        await auth_client.login_with_sms("+441234567890", "123456", country_code="44")

        call_args = mock_client.post.call_args
        assert call_args.kwargs["data"]["countryCode"] == "44"

    @pytest.mark.asyncio
    async def test_refresh_token(self, auth_client, mock_client):
        """Test refreshing token."""
        mock_client.post.return_value = REFRESH_TOKEN_RESPONSE

        result = await auth_client.refresh_token(
            device_id="device_123",
            access_token="old_token",
            refresh_token="old_refresh",
        )

        assert isinstance(result, RefreshTokenResponse)
        assert result.access_token == "new_access_token_xyz"
        assert result.refresh_token == "new_refresh_token_uvw"
        assert result.expires_in == 7200

    @pytest.mark.asyncio
    async def test_refresh_token_request_format(self, auth_client, mock_client):
        """Test refresh token request format."""
        mock_client.post.return_value = REFRESH_TOKEN_RESPONSE

        await auth_client.refresh_token(
            device_id="device_123",
            access_token="old_token",
            refresh_token="old_refresh",
        )

        mock_client.post.assert_called_once_with(
            "userAuth/refreshToken",
            {
                "deviceId": "device_123",
                "accessToken": "old_token",
                "refreshToken": "old_refresh",
            },
            include_token=False,
        )

    @pytest.mark.asyncio
    async def test_add_app_device_info(self, auth_client, mock_client):
        """Test adding app device info."""
        mock_client.post.return_value = {"code": "000000"}

        await auth_client.add_app_device_info("device_123")

        mock_client.post.assert_called_once_with(
            "userAuth/addAppDeviceInfo",
            {
                "deviceId": "device_123",
                "platform": "android",
                "appVersion": "3.0.0",
            },
        )

    @pytest.mark.asyncio
    async def test_add_app_device_info_custom_platform(self, auth_client, mock_client):
        """Test adding app device with custom platform."""
        mock_client.post.return_value = {"code": "000000"}

        await auth_client.add_app_device_info("device_123", platform="ios")

        call_args = mock_client.post.call_args
        assert call_args.kwargs["data"]["platform"] == "ios"

    @pytest.mark.asyncio
    async def test_get_user_info(self, auth_client, mock_client):
        """Test getting user info."""
        mock_client.get.return_value = {
            "code": "000000",
            "data": {"userId": "user_123", "nickName": "Test User"},
        }

        result = await auth_client.get_user_info()

        mock_client.get.assert_called_once_with("userAuth/userBaseInfo")
        assert result["data"]["userId"] == "user_123"

    @pytest.mark.asyncio
    async def test_get_email_code_success(self, auth_client, mock_client):
        """Test getting email code success."""
        mock_client.post.return_value = {"code": "000000"}

        await auth_client.get_email_code("test@example.com")

        mock_client.post.assert_called_once_with(
            "userAuth/getSMSCode",
            {
                "email": "test@example.com",
                "scenario": 0,
                "type": 3,
            },
            include_token=False,
        )
