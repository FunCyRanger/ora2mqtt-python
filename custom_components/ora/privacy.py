"""Privacy sanitization for logging."""

import re
from typing import Any

PRIVACY_KEYS_REDACT = frozenset(
    key.lower()
    for key in [
        "email",
        "password",
        "smsCode",
        "securityPassword",
        "accessToken",
        "access_token",
        "refreshToken",
        "refresh_token",
        "phone",
        "deviceId",
        "device_id",
        "vin",
        "userId",
        "nickName",
        "nick_name",
        "beanId",
        "bean_id",
        "gwId",
        "gw_id",
        "engineNo",
        "vehicleId",
        "id",
        "imsi",
        "simIccid",
    ]
)

PRIVACY_KEYS_MASK = frozenset(
    key.lower()
    for key in [
        "latitude",
        "longitude",
    ]
)

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def mask_privacy_string(s: str) -> str:
    """Mask a privacy-sensitive string, keeping first and last character.

    If the masked portion is > 10 characters, abbreviate with count.
    """
    if not isinstance(s, str) or len(s) <= 2:
        return s
    middle = len(s) - 2
    if middle <= 10:
        return s[0] + "X" * middle + s[-1]
    return f"{s[0]}..{middle}..{s[-1]}"


def is_privacy_value(key: str, value: Any) -> bool:
    """Check if a key/value pair contains privacy-sensitive string data."""
    if key.lower() in PRIVACY_KEYS_REDACT:
        return True
    if isinstance(value, str) and _EMAIL_REGEX.match(value):
        return True
    return False


def _is_lat_lon(key: str, value: Any) -> bool:
    """Check if key/value is a GPS coordinate."""
    return key.lower() in PRIVACY_KEYS_MASK and isinstance(value, (int, float))


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize a value, masking non-privacy string values."""
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return mask_privacy_string(value)
    return value


def sanitize_for_logging(data: dict | None) -> dict | None:
    """Remove sensitive data from dict for logging.

    Privacy keys get masked (first/last char kept, middle X or X..N..X).
    Lat/lon numeric values get ***REDACTED***.
    Non-privacy string values get partially masked (first/last char kept).
    """
    if data is None:
        return None

    sanitized = {}
    for key, value in data.items():
        if _is_lat_lon(key, value):
            sanitized[key] = "***REDACTED***"
        elif is_privacy_value(key, value):
            sanitized[key] = mask_privacy_string(str(value))
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_for_logging(item) if isinstance(item, dict) else _sanitize_value(item)
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def sanitize_url(url: str) -> str:
    """Mask VIN and deviceId in URL query parameters."""
    result = url
    for param in ["vin", "deviceId", "seqNo"]:
        pattern = re.compile(rf"({re.escape(param)}=)([^&\s]+)")
        result = pattern.sub(lambda m: m.group(1) + mask_privacy_string(m.group(2)), result)
    return result