"""Integration tests for API client."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.ora.api.client import GwmApiException, GwmHttpClient
from custom_components.ora.privacy import (
    is_privacy_value,
    mask_privacy_string,
    sanitize_for_logging,
    sanitize_url,
)
from tests.fixtures.api_responses import (
    ERROR_OTHER_308025,
    ERROR_RATE_LIMIT_308024,
    ERROR_RESPONSE,
    LOGIN_SUCCESS_RESPONSE,
    TOKEN_EXPIRED_RESPONSE,
)


class TestMaskPrivacyString:
    """Test mask_privacy_string function."""

    def test_short_strings_unchanged(self):
        """Strings <= 2 chars are returned unchanged."""
        assert mask_privacy_string("a") == "a"
        assert mask_privacy_string("ab") == "ab"
        assert mask_privacy_string("") == ""

    def test_non_string_unchanged(self):
        """Non-string values are returned unchanged."""
        assert mask_privacy_string(123) == 123
        assert mask_privacy_string(None) is None

    def test_exact_12_chars_abbreviated(self):
        """Middle 12 chars -> abbreviated X..12..X."""
        s = "helloworldxy"
        assert mask_privacy_string(s) == "hXXXXXXXXXXy"

    def test_exact_11_chars_not_abbreviated(self):
        """Middle 11 chars -> no abbreviation."""
        s = "helloworldx"
        assert mask_privacy_string(s) == "hXXXXXXXXXx"

    def test_exact_10_chars_not_abbreviated(self):
        """Middle 10 chars -> no abbreviation."""
        s = "helloworld"
        assert mask_privacy_string(s) == "hXXXXXXXXd"

    def test_short_middle_kept(self):
        """Middle <= 10 chars: first + X*middle + last."""
        assert mask_privacy_string("abc") == "aXc"
        assert mask_privacy_string("abcd") == "aXXd"
        assert mask_privacy_string("abcde") == "aXXXe"
        assert mask_privacy_string("abcdefghijk") == "aXXXXXXXXXk"
        assert mask_privacy_string("abcdefghijkl") == "aXXXXXXXXXXl"

    def test_long_email_abbreviated(self):
        """Long emails are abbreviated."""
        assert mask_privacy_string("verylongemail@x.de") == "v..16..e"

    def test_phone_masked_abbreviated(self):
        """Phone numbers with >10 middle chars are abbreviated."""
        assert mask_privacy_string("+491234567890") == "+..11..0"

    def test_vin_masked_abbreviated(self):
        """VINs are masked and abbreviated."""
        assert mask_privacy_string("LHG12345678901234") == "L..15..4"

    def test_device_id_masked(self):
        """Device IDs are masked."""
        assert mask_privacy_string("abc123def") == "aXXXXXXXf"
        assert mask_privacy_string("abc123defghijkl") == "a..13..l"


class TestIsPrivacyValue:
    """Test is_privacy_value function."""

    def test_privacy_keys(self):
        """Known privacy keys return True."""
        assert is_privacy_value("email", "test@example.com") is True
        assert is_privacy_value("password", "secret") is True
        assert is_privacy_value("deviceId", "device123") is True
        assert is_privacy_value("vin", "LHG12345678901234") is True
        assert is_privacy_value("accessToken", "token123") is True

    def test_email_pattern(self):
        """Strings matching email pattern return True even for non-privacy keys."""
        assert is_privacy_value("username", "user@example.com") is True
        assert is_privacy_value("data", "foo@bar.com") is True

    def test_non_email_strings(self):
        """Non-email strings return False."""
        assert is_privacy_value("name", "John Doe") is False
        assert is_privacy_value("value", "12345") is False

    def test_non_string_value(self):
        """Non-string values return False unless key is privacy key."""
        assert is_privacy_value("name", 123) is False
        assert is_privacy_value("name", None) is False
        assert is_privacy_value("email", 123) is True


class TestSanitizeUrl:
    """Test sanitize_url function."""

    def test_vin_in_url_masked(self):
        """VIN query param is masked."""
        url = "https://api.example.com/vehicle/getLastStatus?vin=LHG12345678901234&seqNo="
        result = sanitize_url(url)
        assert "LHG12345678901234" not in result
        assert "L..15..4" in result

    def test_device_id_in_url_masked(self):
        """deviceId query param is masked."""
        url = "https://api.example.com/vehicle/T5/sendCmd?vin=ABC123&deviceId=abc123def"
        result = sanitize_url(url)
        assert "abc123def" not in result
        assert "aXXXXXXXf" in result

    def test_seq_no_in_url_masked(self):
        """seqNo query param is masked."""
        url = "https://api.example.com/vehicle/getRemoteCtrlResultT5?seqNo=T5SEQ001234"
        result = sanitize_url(url)
        assert "T5SEQ001234" not in result

    def test_no_match_unchanged(self):
        """URLs without privacy params are unchanged."""
        url = "https://api.example.com/vehicle/getLastStatus?other=value"
        assert sanitize_url(url) == url

    def test_empty_value_unchanged(self):
        """Empty value is unchanged."""
        url = "https://api.example.com/vehicle/getLastStatus?vin=&seqNo="
        assert "vin=" in sanitize_url(url)

    def test_multiple_params(self):
        """Multiple privacy params are all masked."""
        url = "https://api.example.com/vehicle/getLastStatus?vin=LHG12345678901234&deviceId=dev123456789"
        result = sanitize_url(url)
        assert "LHG12345678901234" not in result
        assert "dev123456789" not in result


class TestSanitizeForLogging:
    """Test sanitize_for_logging function."""

    def test_none(self):
        """None input returns None."""
        assert sanitize_for_logging(None) is None

    def test_privacy_keys_masked(self):
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "email": "test@example.com",
            "password": "secret123",
            "deviceId": "device123",
            "vin": "LHG12345678901234",
            "accessToken": "eyJhbGciOiJIUzI1NiJ9",
            "refreshToken": "refresh123",
            "smsCode": "123456",
            "securityPassword": "hashedpin",
            "phone": "+491234567890",
            "userId": "user123",
            "latitude": 52.52,
            "longitude": 13.4,
        })
        for key, value in {
            "email": "test@example.com",
            "password": "secret123",
            "deviceId": "device123",
            "vin": "LHG12345678901234",
            "accessToken": "eyJhbGciOiJIUzI1NiJ9",
            "refreshToken": "refresh123",
            "smsCode": "123456",
            "securityPassword": "hashedpin",
            "phone": "+491234567890",
            "userId": "user123",
        }.items():
            assert result[key] == mask_privacy_string(str(value)), f"{key} should be masked"
        assert result["latitude"] == "***REDACTED***"
        assert result["longitude"] == "***REDACTED***"

    def test_non_privacy_values_unchanged(self):
        """Non-privacy values are unchanged."""
        result = sanitize_for_logging({
            "code": "000000",
            "description": "Success",
            "country": "DE",
        })
        assert result["code"] == "000000"
        assert result["description"] == "Success"
        assert result["country"] == "DE"

    def test_nested_dict_sanitized(self):
        """Nested dicts are recursively sanitized."""
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "outer": {
                "email": "nested@example.com",
                "normal": "value",
            }
        })
        assert result["outer"]["email"] == mask_privacy_string("nested@example.com")
        assert result["outer"]["normal"] == "value"

    def test_list_with_dicts_sanitized(self):
        """Lists containing dicts are recursively sanitized."""
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "items": [
                {"email": "a@b.com", "type": "user"},
                {"email": "c@d.com", "type": "admin"},
            ]
        })
        assert result["items"][0]["email"] == mask_privacy_string("a@b.com")
        assert result["items"][1]["email"] == mask_privacy_string("c@d.com")
        assert result["items"][0]["type"] == "user"

    def test_email_as_value_masked(self):
        """Email-like strings in non-privacy keys are masked."""
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "username": "user@example.com",
            "normalField": "not.an.email",
        })
        assert result["username"] == mask_privacy_string("user@example.com")
        assert result["normalField"] == "not.an.email"


class TestSanitizeResponseForLogging:
    """Test sanitize_for_logging function."""

    def test_none(self):
        """None input returns None."""
        assert sanitize_for_logging(None) is None

    def test_privacy_keys_masked_response(self):
        """Privacy keys in responses are masked."""
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "code": "000000",
            "data": {
                "userId": "user_123456",
                "nickName": "Test User",
                "phone": "+491234567890",
                "accessToken": "token123",
                "refreshToken": "refresh456",
            }
        })
        for key, value in {
            "userId": "user_123456",
            "nickName": "Test User",
            "phone": "+491234567890",
            "accessToken": "token123",
            "refreshToken": "refresh456",
        }.items():
            assert result["data"][key] == mask_privacy_string(str(value)), f"{key} should be masked"
        assert result["code"] == "000000"

    def test_vehicle_status_response_sanitized(self):
        """Vehicle status response has VIN, lat/lon, deviceId masked/redacted."""
        from custom_components.ora.privacy import mask_privacy_string
        response = {
            "code": "000000",
            "data": {
                "vin": "LHG12345678901234",
                "deviceId": "device_001",
                "latitude": 52.520008,
                "longitude": 13.404954,
                "acquisitionTime": 1704067200000,
                "items": [
                    {"code": "2013021", "value": "75", "unit": "%"},
                ],
            }
        }
        result = sanitize_for_logging(response)
        assert result["data"]["vin"] == mask_privacy_string("LHG12345678901234")
        assert result["data"]["deviceId"] == mask_privacy_string("device_001")
        assert result["data"]["latitude"] == "***REDACTED***"
        assert result["data"]["longitude"] == "***REDACTED***"
        assert result["data"]["acquisitionTime"] == 1704067200000
        assert result["data"]["items"][0]["value"] == "75"


class TestGwmHttpClient:
    """Test GwmHttpClient."""

    @pytest.fixture
    def client(self):
        return GwmHttpClient(region="eu")

    def test_client_initialization(self, client):
        """Test client is initialized correctly."""
        assert client._region == "eu"
        assert client._access_token is None
        assert client._country == "DE"
        assert "eu-h5-gateway.gwmcloud.com" in client._h5_base
        assert "eu-app-gateway.gwmcloud.com" in client._app_base

    def test_set_access_token(self, client):
        """Test setting access token."""
        client.set_access_token("test_token")
        assert client.access_token == "test_token"

        client.set_access_token(None)
        assert client.access_token is None

    def test_country_setter(self, client):
        """Test country setter clears token."""
        client.set_access_token("test_token")
        client.country = "GB"
        assert client.country == "GB"
        assert client._access_token is None  # Token cleared on country change

    def test_language_setter(self, client):
        """Test language setter."""
        client.language = "de"
        assert client.language == "de"

    def test_build_headers_without_token(self, client):
        """Test header building without token."""
        headers = client._build_headers(include_token=False)
        assert "rs" in headers
        assert "terminal" in headers
        assert "accessToken" not in headers

    def test_build_headers_with_token(self, client):
        """Test header building with token."""
        client.set_access_token("test_token")
        headers = client._build_headers(include_token=True)
        assert headers["accessToken"] == "test_token"

    @pytest.mark.asyncio
    async def test_response_validation_success(self, client):
        """Test successful response validation."""
        result = client._check_response({"code": "000000", "description": "Success"})
        assert result["code"] == "000000"

    @pytest.mark.asyncio
    async def test_response_validation_error(self, client):
        """Test error response validation."""
        with pytest.raises(GwmApiException) as exc_info:
            client._check_response(ERROR_RESPONSE)
        assert exc_info.value.code == "100001"
        assert exc_info.value.message == "Invalid parameter"

    @pytest.mark.asyncio
    async def test_response_validation_token_expired(self, client):
        """Test token expired response validation."""
        with pytest.raises(GwmApiException) as exc_info:
            client._check_response(TOKEN_EXPIRED_RESPONSE)
        assert exc_info.value.code == "110002"


class TestGwmHttpClientRequests:
    """Test HTTP request methods."""

    @pytest.fixture
    def client(self):
        return GwmHttpClient(region="eu")

    @pytest.mark.asyncio
    async def test_get_request(self, client):
        """Test GET request."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": "000000"}
            result = await client.get("userAuth/userBaseInfo")
            assert result["code"] == "000000"

    @pytest.mark.asyncio
    async def test_get_request_app_gateway(self, client):
        """Test GET request to app gateway."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": "000000"}
            result = await client.get("globalapp/vehicle/acquireVehicles", use_app_gateway=True)
            assert result["code"] == "000000"

    @pytest.mark.asyncio
    async def test_post_request(self, client):
        """Test POST request."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": "000000"}
            result = await client.post(
                "userAuth/loginWithSMS",
                {"phone": "+491234567890", "smsCode": "123456"},
            )
            assert result["code"] == "000000"

    @pytest.mark.asyncio
    async def test_post_request_without_token(self, client):
        """Test POST request without token."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": "000000"}
            result = await client.post(
                "userAuth/getSMSCode",
                {"phone": "+491234567890"},
                include_token=False,
            )
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert kwargs.get("include_token") is False

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing session."""
        mock_session = AsyncMock()
        client._session = mock_session
        client._owns_session = True

        await client.close()

        mock_session.close.assert_called_once()
        assert client._session is None


class TestExceptionHandling:
    """Test exception handling for config flow workflows."""

    @pytest.fixture
    def client(self):
        return GwmHttpClient(region="eu")

    def test_rate_limit_308024_raises_exception(self, client):
        """Test rate limit error 308024 raises GwmApiException."""
        with pytest.raises(GwmApiException) as exc_info:
            client._check_response(ERROR_RATE_LIMIT_308024)
        assert exc_info.value.code == "308024"
        assert "Rate limit" in exc_info.value.message

    def test_other_error_code_raises_exception(self, client):
        """Test other error codes raise GwmApiException."""
        with pytest.raises(GwmApiException) as exc_info:
            client._check_response(ERROR_OTHER_308025)
        assert exc_info.value.code == "308025"
        assert exc_info.value.message == "Some other error"

    def test_success_response_no_exception(self, client):
        """Test successful response does not raise exception."""
        result = client._check_response(LOGIN_SUCCESS_RESPONSE)
        assert result["code"] == "000000"
