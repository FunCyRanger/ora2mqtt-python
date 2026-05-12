"""GWM API client."""

import logging

from .auth import (
    CustomerServicePhone,
    GwmAuthClient,
    LoginResponse,
    RefreshTokenResponse,
)
from .cert import CertificateHandler
from .client import GwmApiException, GwmHttpClient
from .vehicles import (
    GwmVehicleClient,
    RemoteCtrlResult,
    Vehicle,
    VehicleStatus,
    VehicleStatusItem,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "GwmApiException",
    "GwmHttpClient",
    "GwmAuthClient",
    "GwmVehicleClient",
    "CertificateHandler",
    "LoginResponse",
    "RefreshTokenResponse",
    "CustomerServicePhone",
    "Vehicle",
    "VehicleStatus",
    "VehicleStatusItem",
    "RemoteCtrlResult",
]


class GwmApi:
    """Combined GWM API client."""

    def __init__(
        self,
        region: str = "eu",
        cert_path: str | None = None,
        session: None = None,
        cert_handler: CertificateHandler | None = None,
    ):
        if cert_handler is None and cert_path is None:
            from pathlib import Path

            cert_dir = Path(__file__).parent.parent / "cert"
            if cert_dir.exists():
                cert_handler = CertificateHandler(cert_dir)

        self._cert_handler = cert_handler
        self._client = GwmHttpClient(region, cert_path, session, cert_handler)
        self.auth = GwmAuthClient(self._client)
        self.vehicles = GwmVehicleClient(self._client)
        _LOGGER.info("ORA: GwmApi created region=%s", region)

    def set_access_token(self, token: str | None):
        """Set the access token."""
        self._client.set_access_token(token)
        _LOGGER.info("ORA: access token %s", "set" if token else "cleared")

    @property
    def access_token(self) -> str | None:
        return self._client.access_token

    @property
    def country(self) -> str:
        return self._client.country

    @country.setter
    def country(self, value: str):
        self._client.country = value

    async def close(self):
        """Close the client."""
        _LOGGER.info("ORA: GwmApi closing")
        await self._client.close()
        _LOGGER.info("ORA: GwmApi closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
