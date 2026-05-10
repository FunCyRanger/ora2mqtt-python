"""Integration tests for certificate handling."""

from math import lcm
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from custom_components.ora.api.cert import (
    CertificateHandler,
    _untransform,
)


class TestUntransform:
    """Test the untransform function."""

    def test_untransform_known_value(self):
        """Test untransform with known encoded value.

        For d=0b100010 (MSB=1, LSB=2), the server-side encoding applies
        h(v) = (v & 0xF8) | (((v & 7) - 3) & 7) to each non-MSB chunk:
        encoded = MSB << 5 | h(2) = 32 | 7 = 39.
        _untransform reverses via g(v) = (v & 0xF8) + ((v + 3) & 7).
        """
        assert _untransform(39, 10) == 34

    def test_untransform_none_zero(self):
        """Test untransform with non-zero value."""
        result = _untransform(1, 10)
        assert isinstance(result, int)


class TestRsaBuiltins:
    """Test cryptography RSA built-in functions replace removed custom code."""

    def test_gcd_basic(self):
        """Test basic GCD via cryptography."""
        assert rsa.gcd(48, 18) == 6

    def test_gcd_coprime(self):
        """Test coprime numbers."""
        assert rsa.gcd(17, 13) == 1

    def test_gcd_same(self):
        """Test same numbers."""
        assert rsa.gcd(15, 15) == 15

    def test_mod_inverse_basic(self):
        """Test modular inverse via cryptography."""
        p = 61
        q = 53
        e = 17
        carmichael = lcm(p - 1, q - 1)
        d = rsa.rsa_recover_private_exponent(e, p, q)
        assert (e * d) % carmichael == 1

    def test_recover_prime_factors(self):
        """Test P/Q recovery via cryptography built-in."""
        p = 61
        q = 53
        n = p * q
        e = 17
        phi = (p - 1) * (q - 1)
        d = pow(e, -1, phi)

        recovered_p, recovered_q = rsa.rsa_recover_prime_factors(n, e, d)
        assert {recovered_p, recovered_q} == {p, q}


class TestParseTransformedKey:
    """Test parsing of transformed key."""

    def test_parse_der_integer(self):
        """Test parsing a DER integer."""
        from custom_components.ora.api.cert import _parse_der_integer

        data = bytes([0x02, 0x03, 0x01, 0x00, 0x01])
        value, consumed = _parse_der_integer(data, 0)
        assert value == 65537
        assert consumed == 5

    def test_parse_simple_key(self):
        """Test parsing a simple key."""
        from custom_components.ora.api.cert import _parse_der_sequence

        simple_key = bytes(
            [
                0x30,
                0x0A,
                0x02,
                0x03,
                0x01,
                0x00,
                0x01,
                0x02,
                0x03,
                0x01,
                0x00,
                0x01,
            ]
        )

        contents, consumed = _parse_der_sequence(simple_key, 0)
        assert consumed == 12


class TestCertificateHandler:
    """Test CertificateHandler class."""

    @pytest.fixture
    def cert_dir(self, tmp_path):
        """Create temp cert directory with test certs."""
        cert_dir = tmp_path / "cert"
        cert_dir.mkdir()

        test_cert = b"""-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAMJTUt3kM4FaMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnVu
c3dlZDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC8j8+kL1KPY8cCQQC8j8+kL1KPY8
CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8AgMBAAEw
DQYJKoZIhvcNAQELBQADQQB4X8a3cZ9vCQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8
j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KP
-----END CERTIFICATE-----"""
        cert_dir.joinpath("gwm_general.cer").write_bytes(test_cert)

        test_key = b"""MIICHwIBAAKCAQEAr2D3wgi/qtvTqvc9Nk5BPCCoiZCqBcCCAdRkXgkzwT1aXe7kTegyi
PkhZ++j/vU1enKrylHL/Db3CHEdtZYvge9JAN8oeFJfRqGcypcG7L7EF21Yn+SPFFVm12
XB2TE/D2Adn8qQ3uElt5pJir/gGX4kLOU11LtADX7N8T3ujqNbmuEtx993mwwOmNIC05
5gvHsJD42XxFJnLAbusq7usrUYbcmjmuX1tn/UJUsVmzXoFipmhNq/oOXG18J5UfKoFtd
sFYnlj/GeGv+6PUgFX/uYVtBwsT/4go5HR3FksTWw2XC1QYJEvgCcX75STtT1NPEJiJm
N2zEvO4pHv2G8zwIBAQKCAQEApv0XGYjck2la7MyverEhPTPUyio718Gw5OLzQj7xFvG
htdL0PjcImIDphbdvEWeUFYTHF+73B0ocOkvFCjLfwcm9NBuzXiRB1mti972tAfDC5qI
af4Vo0lR6aey3mr4iq6iB+ynwtPDEhPGWf13f7gVOkgacMVQXjtlv8Rec0qDiE4QOuRC
wnPNffXUrnVkCQ7yed1WAbZ98OKAB2zyQKyJkHyYAFW6JluiUBZDvGK6WFMI49KZLNl8
gBl/22/RCn3+xwKYqysyd9PMjakk88iIl+fkDtVQAk760vflMR1IFXM1xsHh/56aBlTV
zKxSMIMvFmQCmRvBphY28/Q76BgIBAQIBAQIBAQIBAQIBAQ==
"""
        cert_dir.joinpath("gwm_general.key").write_bytes(test_key)

        test_chain = b"""-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAMJTUt3kM4FaMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnVu
c3dlZDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC8j8+kL1KPY8cCQQC8j8+kL1KPY8
CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KPY8AgMBAAEw
DQYJKoZIhvcNAQELBQADQQB4X8a3cZ9vCQQC8j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8
j8+kL1KPY8CQQC8j8+kL1KPY8CQQC8j8+kL1KP
-----END CERTIFICATE-----"""
        cert_dir.joinpath("gwm_root.pem").write_bytes(test_chain)

        return cert_dir

    def test_certificate_handler_init(self, cert_dir):
        """Test CertificateHandler initialization."""
        handler = CertificateHandler(cert_dir)
        assert handler._cert_dir == cert_dir

    def test_load_certificate(self, cert_dir):
        """Test loading certificate."""
        handler = CertificateHandler(cert_dir)
        cert = handler.certificate
        assert cert is not None
        from cryptography import x509

        assert isinstance(cert, x509.Certificate)

    def test_load_chain(self, cert_dir):
        """Test loading certificate chain."""
        handler = CertificateHandler(cert_dir)
        chain = handler.chain
        assert len(chain) >= 1
        from cryptography import x509

        assert all(isinstance(c, x509.Certificate) for c in chain)

    def test_certificate_with_key_property(self, cert_dir):
        """Test certificate_with_key property."""
        handler = CertificateHandler(cert_dir)
        cert, key = handler.certificate_with_key
        assert cert is not None
        assert key is not None
        assert isinstance(key, rsa.RSAPrivateKey)


class TestCertificateHandlerRealCerts:
    """Test with real certificates from the repo."""

    def test_real_certificates_exist(self):
        """Test that real certificate files exist."""
        cert_dir = Path(__file__).parent.parent / "custom_components" / "ora" / "cert"

        assert (cert_dir / "gwm_general.cer").exists()
        assert (cert_dir / "gwm_general.key").exists()
        assert (cert_dir / "gwm_root.pem").exists()

    def test_load_real_certificate(self):
        """Test loading real certificate."""
        cert_dir = Path(__file__).parent.parent / "custom_components" / "ora" / "cert"
        handler = CertificateHandler(cert_dir)

        cert = handler.certificate
        assert cert is not None

    def test_load_real_key(self):
        """Test loading real key."""
        cert_dir = Path(__file__).parent.parent / "custom_components" / "ora" / "cert"
        handler = CertificateHandler(cert_dir)

        cert, key = handler.certificate_with_key
        assert cert is not None
        assert key is not None
        assert isinstance(key, rsa.RSAPrivateKey)

        key_size = key.key_size
        assert key_size >= 2048

    def test_real_chain(self):
        """Test loading real chain."""
        cert_dir = Path(__file__).parent.parent / "custom_components" / "ora" / "cert"
        handler = CertificateHandler(cert_dir)

        chain = handler.chain
        assert len(chain) >= 1
