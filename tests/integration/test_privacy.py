"""Tests for privacy module."""

import pytest

from custom_components.ora.privacy import (
    _is_lat_lon,
    is_privacy_value,
    mask_privacy_string,
    sanitize_for_logging,
    sanitize_url,
)


class TestMaskPrivacyStringPrivacy:
    """Test mask_privacy_string."""

    def test_short_strings_unchanged(self):
        assert mask_privacy_string("a") == "a"
        assert mask_privacy_string("ab") == "ab"
        assert mask_privacy_string("") == ""

    def test_non_string_unchanged(self):
        assert mask_privacy_string(123) == 123
        assert mask_privacy_string(None) is None

    def test_exact_12_chars_abbreviated(self):
        assert mask_privacy_string("helloworldxy") == "hXXXXXXXXXXy"

    def test_exact_11_chars_not_abbreviated(self):
        assert mask_privacy_string("helloworldx") == "hXXXXXXXXXx"

    def test_exact_10_chars_not_abbreviated(self):
        assert mask_privacy_string("helloworld") == "hXXXXXXXXd"

    def test_short_middle_kept(self):
        assert mask_privacy_string("abc") == "aXc"
        assert mask_privacy_string("abcd") == "aXXd"
        assert mask_privacy_string("abcde") == "aXXXe"
        assert mask_privacy_string("abcdefghijk") == "aXXXXXXXXXk"
        assert mask_privacy_string("abcdefghijkl") == "aXXXXXXXXXXl"

    def test_long_email_abbreviated(self):
        assert mask_privacy_string("verylongemail@x.de") == "v..16..e"

    def test_phone_masked_abbreviated(self):
        assert mask_privacy_string("+491234567890") == "+..11..0"

    def test_vin_masked_abbreviated(self):
        assert mask_privacy_string("LHG12345678901234") == "L..15..4"

    def test_device_id_masked(self):
        assert mask_privacy_string("abc123def") == "aXXXXXXXf"
        assert mask_privacy_string("abc123defghijkl") == "a..13..l"


class TestIsPrivacyValuePrivacy:
    """Test is_privacy_value."""

    def test_privacy_keys(self):
        assert is_privacy_value("email", "test@example.com") is True
        assert is_privacy_value("password", "secret") is True
        assert is_privacy_value("deviceId", "device123") is True
        assert is_privacy_value("vin", "LHG12345678901234") is True
        assert is_privacy_value("accessToken", "token123") is True

    def test_email_pattern(self):
        assert is_privacy_value("username", "user@example.com") is True
        assert is_privacy_value("data", "foo@bar.com") is True

    def test_non_email_strings(self):
        assert is_privacy_value("name", "John Doe") is False
        assert is_privacy_value("value", "12345") is False

    def test_non_string_value(self):
        assert is_privacy_value("name", 123) is False
        assert is_privacy_value("name", None) is False
        assert is_privacy_value("email", 123) is True


class TestIsLatLon:
    """Test _is_lat_lon."""

    def test_latitude_longitude_numerics(self):
        assert _is_lat_lon("latitude", 52.52) is True
        assert _is_lat_lon("longitude", 13.4) is True
        assert _is_lat_lon("latitude", 123) is True
        assert _is_lat_lon("Latitude", 52.52) is True
        assert _is_lat_lon("LATITUDE", 52.52) is True

    def test_non_numeric_not_lat_lon(self):
        assert _is_lat_lon("latitude", "52.52") is False
        assert _is_lat_lon("latitude", None) is False

    def test_non_lat_lon_keys(self):
        assert _is_lat_lon("email", "test@example.com") is False
        assert _is_lat_lon("code", 52.52) is False


class TestSanitizeUrlPrivacy:
    """Test sanitize_url."""

    def test_vin_in_url_masked(self):
        url = "https://api.example.com/vehicle/getLastStatus?vin=LHG12345678901234&seqNo="
        result = sanitize_url(url)
        assert "LHG12345678901234" not in result
        assert "L..15..4" in result

    def test_device_id_in_url_masked(self):
        url = "https://api.example.com/vehicle/T5/sendCmd?vin=ABC123&deviceId=abc123def"
        result = sanitize_url(url)
        assert "abc123def" not in result
        assert "aXXXXXXXf" in result

    def test_seq_no_in_url_masked(self):
        url = "https://api.example.com/vehicle/getRemoteCtrlResultT5?seqNo=T5SEQ001234"
        result = sanitize_url(url)
        assert "T5SEQ001234" not in result

    def test_no_match_unchanged(self):
        url = "https://api.example.com/vehicle/getLastStatus?other=value"
        assert sanitize_url(url) == url

    def test_empty_value_unchanged(self):
        url = "https://api.example.com/vehicle/getLastStatus?vin=&seqNo="
        assert "vin=" in sanitize_url(url)

    def test_multiple_params(self):
        url = "https://api.example.com/vehicle/getLastStatus?vin=LHG12345678901234&deviceId=dev123456789"
        result = sanitize_url(url)
        assert "LHG12345678901234" not in result
        assert "dev123456789" not in result


class TestSanitizeForLoggingPrivacy:
    """Test sanitize_for_logging from privacy module."""

    def test_none(self):
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
            "beanId": "bean123",
            "gwId": "gw123",
            "engineNo": "ENG1234567",
            "vehicleId": "veh_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e",
            "id": "rec_abc123def456abc123def456abc123def456_0_STATUS",
            "imsi": "imsi_123456789012345",
            "simIccid": "8976123456789012345",
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
            "beanId": "bean123",
            "gwId": "gw123",
            "engineNo": "ENG1234567",
            "vehicleId": "veh_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e",
            "id": "rec_abc123def456abc123def456abc123def456_0_STATUS",
            "imsi": "imsi_123456789012345",
            "simIccid": "8976123456789012345",
        }.items():
            assert result[key] == mask_privacy_string(str(value)), f"{key} should be masked"
        assert result["latitude"] == "***REDACTED***"
        assert result["longitude"] == "***REDACTED***"

    def test_non_privacy_values_unchanged(self):
        result = sanitize_for_logging({
            "code": "000000",
            "description": "Success",
            "country": "DE",
        })
        assert result["code"] == "000000"
        assert result["description"] == "Success"
        assert result["country"] == "DE"

    def test_nested_dict_sanitized(self):
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
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "username": "user@example.com",
            "normalField": "not.an.email",
        })
        assert result["username"] == mask_privacy_string("user@example.com")
        assert result["normalField"] == "not.an.email"

    def test_user_input_dict_full(self):
        from custom_components.ora.privacy import mask_privacy_string
        result = sanitize_for_logging({
            "access_token": "eyJhbGciOiJSUzI1NiJ9...",
            "refresh_token": "eyJhbGciOiJSUzI1NiJ9...",
            "email": "test@user.example.com",
            "bean_id": "bean_1234567890",
            "device_id": "dev_abc123def456",
            "gw_id": "gw_123456789",
            "region": "eu",
        })
        for key, value in {
            "access_token": "eyJhbGciOiJSUzI1NiJ9...",
            "refresh_token": "eyJhbGciOiJSUzI1NiJ9...",
            "email": "test@user.example.com",
            "bean_id": "bean_1234567890",
            "device_id": "dev_abc123def456",
            "gw_id": "gw_123456789",
        }.items():
            assert result[key] == mask_privacy_string(str(value)), f"{key} should be masked"
        assert result["region"] == "eu"