"""Authentication methods for GWM API."""

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..privacy import mask_privacy_string
from .client import GwmHttpClient

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


@dataclass
class LoginResponse:
    """Login response data."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    gw_id: str = ""
    bean_id: str = ""


@dataclass
class RefreshTokenResponse:
    """Token refresh response."""

    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class CustomerServicePhone:
    """Customer service phone info."""

    phone: str
    country_code: str


@dataclass
class Country:
    """Country information."""

    code: str
    name: str
    lang_code: str


@dataclass
class Countrys:
    """List of countries."""

    countries: list[Country]


class GwmAuthClient:
    """Authentication client for GWM API."""

    def __init__(self, client: GwmHttpClient):
        self._client = client

    async def get_sms_code(
        self,
        phone: str,
        country_code: str = "49",
    ) -> None:
        """Request SMS code for login fallback (when password login requires verification)."""
        _LOGGER.info("ORA: get_sms_code phone=%s country=%s", phone[-4:], country_code)
        await self._client.post(
            "userAuth/getSMSCode",
            {
                "phone": phone,
                "countryCode": country_code,
                "captchaCode": "",
                "captchaId": "",
            },
            include_token=False,
        )

    async def get_email_code(
        self,
        email: str,
    ) -> None:
        """Request email verification code."""
        _LOGGER.info("ORA: get_email_code email=%s", mask_privacy_string(email))
        await self._client.post(
            "userAuth/getSMSCode",
            {
                "email": email,
                "scenario": 0,
                "type": 3,
            },
            include_token=False,
        )

    async def send_email_code(
        self,
        email: str,
        scenario: int = 0,
    ) -> None:
        """Send email verification code."""
        _LOGGER.info("ORA: send_email_code email=%s scenario=%s", mask_privacy_string(email), scenario)
        await self._client.post(
            "userAuth/getSMSCode",
            {
                "email": email,
                "scenario": scenario,
                "type": 3,
            },
            include_token=False,
        )

    async def verify_email_code(
        self,
        email: str,
        email_code: str,
        device_id: str,
        country: str = "DE",
    ) -> LoginResponse:
        """Login with email verification code."""
        _LOGGER.info(
            "ORA: verify_email_code email=%s device_id=%s country=%s",
            mask_privacy_string(email),
            mask_privacy_string(device_id),
            country,
        )
        result = await self._client.post(
            "userAuth/loginWithSMS",
            {
                "email": email,
                "smsCode": email_code,
                "country": country,
                "deviceId": device_id,
                "model": "P70 Pro",
                "agreement": [1, 2, 23],
                "appType": 0,
            },
            include_token=False,
        )

        data = result.get("data", {})
        _LOGGER.info(
            "ORA: verify_email_code success user_id=%s expires_in=%s",
            data.get("userId", ""),
            data.get("expiresIn", 0),
        )
        return LoginResponse(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            expires_in=int(data.get("expiresIn", 0)),
            user_id=data.get("userId", ""),
            gw_id=data.get("gwId", ""),
            bean_id=data.get("beanId", ""),
        )

    async def login_with_email(
        self,
        email: str,
        password: str,
        device_id: str,
        country: str = "DE",
    ) -> LoginResponse:
        """Login with email and password (primary method)."""
        _LOGGER.info(
            "ORA: login_with_email email=%s device_id=%s country=%s",
            mask_privacy_string(email),
            mask_privacy_string(device_id),
            country,
        )
        result = await self._client.post(
            "userAuth/loginAccount",
            {
                "account": email,
                "agreement": [1, 2, 23],
                "appType": 0,
                "country": country,
                "deviceId": device_id,
                "isEncrypt": False,
                "model": "P70 Pro",
                "password": password,
                "pushToken": "",
                "type": 1,
            },
            include_token=False,
        )

        data = result.get("data", {})
        _LOGGER.info(
            "ORA: login_with_email success user_id=%s expires_in=%s",
            data.get("userId", ""),
            data.get("expiresIn", 0),
        )
        return LoginResponse(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            expires_in=int(data.get("expiresIn", 0)),
            user_id=data.get("userId", ""),
            gw_id=data.get("gwId", ""),
            bean_id=data.get("beanId", ""),
        )

    async def login_with_sms(
        self,
        email: str,
        sms_code: str,
        device_id: str,
        country: str = "DE",
    ) -> LoginResponse:
        """Login with email and SMS code (fallback when password login returns error 110641)."""
        _LOGGER.info("ORA: login_with_sms email=%s device_id=%s", mask_privacy_string(email), mask_privacy_string(device_id))
        result = await self._client.post(
            "userAuth/loginWithSMS",
            {
                "email": email,
                "smsCode": sms_code,
                "country": country,
                "deviceId": device_id,
                "model": "P70 Pro",
            },
            include_token=False,
        )

        data = result.get("data", {})
        return LoginResponse(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            expires_in=int(data.get("expiresIn", 0)),
            user_id=data.get("userId", ""),
            gw_id=data.get("gwId", ""),
            bean_id=data.get("beanId", ""),
        )

    async def refresh_token(
        self,
        device_id: str,
        access_token: str,
        refresh_token: str,
    ) -> RefreshTokenResponse:
        """Refresh the access token."""
        result = await self._client.post(
            "userAuth/refreshToken",
            {
                "deviceId": device_id,
                "accessToken": access_token,
                "refreshToken": refresh_token,
            },
            include_token=False,
        )

        data = result.get("data", {})
        _LOGGER.info("ORA: refresh_token success expires_in=%s", data.get("expiresIn", 0))
        return RefreshTokenResponse(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            expires_in=int(data.get("expiresIn", 0)),
        )

    async def add_app_device_info(
        self,
        device_id: str,
        platform: str = "android",
    ) -> None:
        """Register the app device."""
        _LOGGER.info("ORA: add_app_device_info device_id=%s platform=%s", device_id, platform)
        await self._client.post(
            "userAuth/addAppDeviceInfo",
            {
                "deviceId": device_id,
                "platform": platform,
                "appVersion": "3.0.0",
            },
        )

    async def get_user_info(self) -> dict:
        """Get user base info (validates token)."""
        _LOGGER.info("ORA: get_user_info")
        result = await self._client.get("userAuth/userBaseInfo")
        _LOGGER.info("ORA: get_user_info success")
        return result

    async def get_customer_service_phone(self, country_code: str = "DE") -> CustomerServicePhone:
        """Get customer service phone number."""
        result = await self._client.get(
            f"userAuth/customerServicePhone?countryCode={country_code}",
            include_token=False,
        )

        data = result.get("data", {})
        return CustomerServicePhone(
            phone=data.get("phone", ""),
            country_code=data.get("countryCode", ""),
        )

    def _hash_pin(self, pin: str) -> str:
        """Hash PIN using MD5 (as required by GWM API)."""
        md5 = hashlib.md5(pin.encode("ascii"))
        return md5.hexdigest().lower()

    async def check_security_password(self, pin: str) -> bool:
        """Check if security password (PIN) is correct.

        Returns True if PIN is correct, False otherwise.
        Used for verifying PIN before remote commands.
        """
        _LOGGER.info("ORA: check_security_password")
        hashed_pin = self._hash_pin(pin)
        result = await self._client.post(
            "userAuth/checkSecurityPassword",
            {
                "securityPassword": hashed_pin,
                "type": "2",
            },
        )

        data = result.get("data", {})
        return data.get("isTrue", False)
