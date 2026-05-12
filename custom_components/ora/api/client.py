"""GWM API HTTP client."""

import asyncio
import logging
import os
import ssl
import tempfile
from dataclasses import dataclass
from functools import partial

import aiohttp
from cryptography.hazmat.primitives import serialization

from ..const import REGIONS
from ..privacy import sanitize_for_logging, sanitize_url
from .cert import CertificateHandler

logger = logging.getLogger(__name__)


class GwmApiException(Exception):
    """GWM API error."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class GwmHttpClient:
    """HTTP client for GWM API."""

    def __init__(
        self,
        region: str = "eu",
        cert_path: str | None = None,
        session: aiohttp.ClientSession | None = None,
        cert_handler: CertificateHandler | None = None,
    ):
        self._region = region
        self._cert_path = cert_path
        self._cert_handler = cert_handler
        self._session = session
        self._owns_session = False
        self._ssl_context: ssl.SSLContext | None = None
        self._ssl_context_client: ssl.SSLContext | None = None

        endpoints = REGIONS.get(region, REGIONS["eu"])
        self._h5_base = f"https://{endpoints['h5_gateway']}/app-api/api/v1.0/"
        self._app_base = f"https://{endpoints['app_gateway']}/app-api/api/v1.0/"

        self._headers = {
            "rs": "2",
            "terminal": "GW_APP_ORA",
            "brand": "3",
            "language": "en",
            "systemType": "1",
            "cver": "1.2.0",
        }
        self._access_token: str | None = None
        self._country: str = "DE"

    @property
    def country(self) -> str:
        return self._country

    @country.setter
    def country(self, value: str):
        self._country = value
        self._access_token = None

    @property
    def language(self) -> str:
        return self._headers.get("language", "en")

    @language.setter
    def language(self, value: str):
        self._headers["language"] = value

    @property
    def access_token(self) -> str | None:
        return self._access_token

    def set_access_token(self, token: str | None):
        """Set the access token for API requests."""
        self._access_token = token

    def _create_ssl_context_sync(self, require_client_cert: bool = False) -> ssl.SSLContext:
        """Synchronous SSL context creation (runs in executor).

        Two contexts are cached separately — one without client cert (for h5-gateway)
        and one with the mTLS client cert + intermediate CA chain (for app-gateway).
        """
        if require_client_cert:
            if self._ssl_context_client is not None:
                logger.debug("Returning cached mTLS SSL context")
                return self._ssl_context_client
        else:
            if self._ssl_context is not None:
                logger.debug("Returning cached plain SSL context")
                return self._ssl_context

        logger.debug(
            "Creating new SSL context (require_client_cert=%s, cert_handler=%s)",
            require_client_cert,
            self._cert_handler is not None,
        )
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_default_certs()

        if require_client_cert and self._cert_handler:
            logger.info("Loading client certificate for mTLS")
            cert, key = self._cert_handler.certificate_with_key

            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )

            # Concatenate client cert with intermediate CA chain
            # (matching original C# ora2mqtt behavior — gwm_root.pem intermediates
            # must be sent alongside the client cert for the mTLS handshake)
            chain_pems = self._cert_handler.chain_intermediate_pem()

            combined = cert_pem + chain_pems

            # Lower security level to 0 while loading the cert chain —
            # GWM's intermediate CA cert #3 uses SHA-1 which is rejected at
            # the default security level 2 (OpenSSL 3.x). The actual server
            # will validate chain strength during the TLS handshake.
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
                f.write(combined)
                cert_file = f.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
                f.write(key_pem)
                key_file = f.name

            ctx.load_cert_chain(cert_file, key_file)
            os.unlink(cert_file)
            os.unlink(key_file)

        if require_client_cert:
            self._ssl_context_client = ctx
            logger.debug("mTLS SSL context created and cached")
        else:
            self._ssl_context = ctx
            logger.debug("Plain SSL context created and cached")
        return ctx

    async def _ensure_ssl_context(self, require_client_cert: bool = False) -> ssl.SSLContext:
        """Async SSL context creation that runs in executor to avoid event loop blocking."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(self._create_ssl_context_sync, require_client_cert)
        )

    async def _ensure_session(self, require_client_cert: bool = False) -> aiohttp.ClientSession:
        """Ensure we have a valid session."""
        if self._session is None or self._session.closed:
            ssl_context = await self._ensure_ssl_context(require_client_cert)
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
            self._owns_session = True
        return self._session

    def _build_headers(self, include_token: bool = True) -> dict[str, str]:
        """Build request headers."""
        headers = dict(self._headers)
        headers["country"] = self._country
        if include_token and self._access_token:
            headers["accessToken"] = self._access_token
        return headers

    async def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        data: dict | None = None,
        include_token: bool = True,
        require_client_cert: bool = False,
    ) -> dict:
        """Make an API request."""
        session = await self._ensure_session(require_client_cert)
        url = f"{base_url}{path}"
        headers = self._build_headers(include_token)

        logger.info("Request: %s %s", method, sanitize_url(url))
        if data:
            logger.info("Request data: %s", sanitize_for_logging(data))

        ssl_context = None
        if require_client_cert:
            ssl_context = await self._ensure_ssl_context(require_client_cert)

        async with session.request(
            method,
            url,
            json=data,
            headers=headers,
            ssl=ssl_context,
        ) as response:
            logger.info("Response status: %s", response.status)

            response.raise_for_status()
            result = await response.json()

            logger.info("Response: %s", sanitize_for_logging(result))

            return self._check_response(result)

    def _check_response(self, data: dict) -> dict:
        """Check API response for errors."""
        code = data.get("code", "Unknown")
        description = data.get("description", "Unknown error")
        logger.info("Checking response code: '%s', description: '%s'", code, description)
        if code != "000000":
            logger.warning("API error code: %s, description: %s", code, description)
            raise GwmApiException(code, description)
        return data

    async def get(
        self,
        path: str,
        use_app_gateway: bool = False,
        include_token: bool = True,
    ) -> dict:
        """Make a GET request."""
        base = self._app_base if use_app_gateway else self._h5_base
        require_cert = use_app_gateway and self._cert_handler is not None
        return await self._request(
            "GET", base, path, include_token=include_token, require_client_cert=require_cert
        )

    async def post(
        self,
        path: str,
        data: dict,
        use_app_gateway: bool = False,
        include_token: bool = True,
    ) -> dict:
        """Make a POST request."""
        base = self._app_base if use_app_gateway else self._h5_base
        require_cert = use_app_gateway and self._cert_handler is not None
        return await self._request(
            "POST", base, path, data, include_token, require_client_cert=require_cert
        )

    async def close(self):
        """Close the session."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
