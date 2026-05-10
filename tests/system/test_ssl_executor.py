"""System tests for SSL context and response validation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ora.api.cert import CertificateHandler, parse_transformed_key
from custom_components.ora.api.client import GwmHttpClient


class TestSslContextExecutor:
    """Test SSL context creation uses executor to avoid event loop blocking."""

    def test_create_ssl_context_sync_exists(self):
        """Test _create_ssl_context_sync method exists."""
        client = GwmHttpClient()
        assert hasattr(client, "_create_ssl_context_sync")

    def test_ensure_ssl_context_is_async(self):
        """Test _ensure_ssl_context is an async method."""
        client = GwmHttpClient()
        assert asyncio.iscoroutinefunction(client._ensure_ssl_context)

    @pytest.mark.asyncio
    async def test_ensure_ssl_context_runs_in_executor(self):
        """Test _ensure_ssl_context runs in executor."""
        client = GwmHttpClient()

        with patch.object(client, "_create_ssl_context_sync") as mock_sync:
            mock_sync.return_value = MagicMock()
            result = await client._ensure_ssl_context(require_client_cert=False)

            mock_sync.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_ensure_session_uses_async_ssl(self):
        """Test _ensure_session uses async SSL context."""
        import ssl

        client = GwmHttpClient()

        with patch.object(client, "_ensure_ssl_context", new_callable=AsyncMock) as mock_ssl:
            mock_ssl.return_value = ssl.create_default_context()
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = MagicMock()
                mock_session.closed = False
                mock_session_class.return_value = mock_session

                await client._ensure_session(require_client_cert=False)

                mock_ssl.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_runs_in_executor_when_required(self):
        """Test _request uses async SSL when client cert required."""
        client = GwmHttpClient()

        with patch.object(client, "_ensure_ssl_context") as mock_ssl:
            mock_ssl.return_value = MagicMock()
            with patch.object(client, "_ensure_session") as mock_session:
                mock_session.return_value = MagicMock()
                mock_response = MagicMock()
                mock_response.__aenter__ = AsyncMock()
                mock_response.__aexit__ = AsyncMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.json = AsyncMock(return_value={"code": "000000"})
                mock_session.return_value.request.return_value = mock_response

                await client._request(
                    "GET",
                    "https://test.example.com/",
                    "test",
                    require_client_cert=True,
                )

                mock_ssl.assert_called_once()


class TestResponseValidation:
    """Test that API responses are validated."""

    @pytest.mark.asyncio
    async def test_request_calls_check_response(self):
        """Test _request calls _check_response to validate the response."""
        client = GwmHttpClient()

        with patch.object(client, "_ensure_session") as mock_session:
            mock_session.return_value = MagicMock()
            mock_response = MagicMock()
            mock_response.__aenter__ = AsyncMock()
            mock_response.__aexit__ = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(return_value={"code": "000000", "data": {}})
            mock_session.return_value.request.return_value = mock_response

            with patch.object(
                client, "_check_response", wraps=client._check_response
            ) as mock_check:
                result = await client._request(
                    "GET",
                    "https://test.example.com/",
                    "test",
                )

                mock_check.assert_called_once()

    def test_check_response_raises_on_error_code(self):
        """Test _check_response raises exception on non-000000 code."""
        client = GwmHttpClient()

        with pytest.raises(Exception) as exc_info:
            client._check_response({"code": "308025", "description": "Invalid credentials"})

        assert "308025" in str(exc_info.value)

    def test_check_response_returns_on_success(self):
        """Test _check_response returns data on success."""
        client = GwmHttpClient()

        result = client._check_response({"code": "000000", "data": {"test": "value"}})

        assert result["code"] == "000000"


class TestSslContextCertLoading:
    """Test SSL context always loads client cert when handler available."""

    def _make_cert_mock(self) -> MagicMock:
        """Create a cert mock that returns bytes for public_bytes."""
        cert = MagicMock()
        cert.public_bytes.return_value = b"fake-cert-pem"
        return cert

    def _make_key_mock(self) -> MagicMock:
        """Create a key mock that returns bytes for private_bytes."""
        key = MagicMock()
        key.private_bytes.return_value = b"fake-key-pem"
        return key

    def _make_cert_handler_prop(
        self,
    ) -> tuple[MagicMock, MagicMock]:
        cert = self._make_cert_mock()
        key = self._make_key_mock()
        return cert, key

    def test_creates_context_without_cert_handler(self):
        """_create_ssl_context_sync should create context without error when no handler."""
        client = GwmHttpClient()
        ctx = client._create_ssl_context_sync(require_client_cert=True)
        assert ctx is not None

    @patch("ssl.SSLContext.load_cert_chain")
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    def test_always_loads_cert_when_handler_available(
        self, mock_tempfile, mock_unlink, mock_load_cert_chain
    ):
        """Should load client cert when handler exists, regardless of require_client_cert."""
        mock_tempfile.return_value.__enter__.return_value.name = "/tmp/fake_cert.pem"
        mock_tempfile.return_value.__enter__.return_value.write = MagicMock()

        cert, key = self._make_cert_handler_prop()
        cert_handler = MagicMock()
        cert_handler.certificate_with_key = (cert, key)

        client = GwmHttpClient(cert_handler=cert_handler)
        ctx = client._create_ssl_context_sync(require_client_cert=False)

        assert cert.public_bytes.called  # cert was accessed
        assert ctx is not None

    @patch("ssl.SSLContext.load_cert_chain")
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    def test_always_loads_cert_when_handler_available_with_flag(
        self, mock_tempfile, mock_unlink, mock_load_cert_chain
    ):
        """Should also load client cert when handler exists and require_client_cert=True."""
        mock_tempfile.return_value.__enter__.return_value.name = "/tmp/fake_cert.pem"
        mock_tempfile.return_value.__enter__.return_value.write = MagicMock()

        cert, key = self._make_cert_handler_prop()
        cert_handler = MagicMock()
        cert_handler.certificate_with_key = (cert, key)

        client = GwmHttpClient(cert_handler=cert_handler)
        ctx = client._create_ssl_context_sync(require_client_cert=True)

        assert cert.public_bytes.called
        assert ctx is not None

    @patch("ssl.SSLContext.load_cert_chain")
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    def test_context_is_cached_and_reused(self, mock_tempfile, mock_unlink, mock_load_cert_chain):
        """SSL context should be cached after first creation."""
        mock_tempfile.return_value.__enter__.return_value.name = "/tmp/fake_cert.pem"
        mock_tempfile.return_value.__enter__.return_value.write = MagicMock()

        cert, key = self._make_cert_handler_prop()
        cert_handler = MagicMock()
        cert_handler.certificate_with_key = (cert, key)

        client = GwmHttpClient(cert_handler=cert_handler)
        ctx1 = client._create_ssl_context_sync(require_client_cert=False)

        ctx2 = client._create_ssl_context_sync(require_client_cert=True)

        assert ctx1 is ctx2
        # cert.public_bytes should only be called once (from first context creation)
        cert.public_bytes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_request_sets_require_cert_when_handler_available(self):
        """GET with use_app_gateway=True should set require_client_cert when handler exists."""
        cert_handler = MagicMock(spec=CertificateHandler)
        cert_handler.certificate_with_key = (self._make_cert_mock(), self._make_key_mock())

        client = GwmHttpClient(cert_handler=cert_handler)
        with patch.object(client, "_request") as mock_request:
            mock_request.return_value = {"code": "000000"}
            await client.get("test/path", use_app_gateway=True)

            mock_request.assert_called_once()
            _, kwargs = mock_request.call_args
            assert kwargs["require_client_cert"] is True


class TestParseTransformedKeyEdgeCases:
    """Test parse_transformed_key edge cases."""

    def test_empty_key_data(self):
        """Empty key data should raise ValueError."""
        with pytest.raises(ValueError, match="Key data too short"):
            parse_transformed_key(b"")

    def test_too_short_key_data(self):
        """Key data shorter than 4 decoded bytes should raise ValueError."""
        with pytest.raises(ValueError, match="Key data too short"):
            parse_transformed_key(b"AA==")

    def test_invalid_base64_but_long_enough(self):
        """Bytes that aren't valid base64 but are long enough should fail DER parsing."""
        with pytest.raises(ValueError, match="Expected SEQUENCE tag"):
            parse_transformed_key(b"not-base64-data-that-is-long-enough-to-pass-length-check")
