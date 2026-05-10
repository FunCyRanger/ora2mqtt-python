"""Certificate handling for GWM API."""

import base64
import logging
from pathlib import Path
from typing import Tuple

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

_LOGGER = logging.getLogger(__name__)


def _untransform(d: int, n_bit_len: int) -> int:
    """Reverse the transformation applied to the private key exponent."""
    five_bit_count = n_bit_len // 5
    if n_bit_len % 5 != 0:
        five_bit_count += 1

    # Extract 5-bit chunks LSB first
    five_bit_numbers = []
    temp_d = d
    for _ in range(five_bit_count):
        five_bit_numbers.append(temp_d & 0x1F)
        temp_d >>= 5

    # The encoding puts the untransformed chunk at the MOST significant position.
    # Process MSB-first so chunks[0] (MSB) is taken raw.
    five_bit_numbers.reverse()

    result = five_bit_numbers[0]
    for i in range(1, five_bit_count):
        result <<= 5
        result |= (five_bit_numbers[i] & 0xF8) + ((five_bit_numbers[i] + 3) & 7)

    return result


def _parse_der_integer(data: bytes, offset: int) -> Tuple[int, int]:
    """Parse a DER INTEGER and return (value, bytes_consumed)."""
    if data[offset] != 0x02:
        raise ValueError(f"Expected INTEGER tag (0x02), got {data[offset]:02x}")

    length = data[offset + 1]
    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(data[offset + 2 : offset + 2 + num_bytes], "big")

    value_start = offset + 2 + (data[offset + 1] & 0x80 and (data[offset + 1] & 0x7F) or 0)
    if data[offset + 1] & 0x80:
        num_bytes = data[offset + 1] & 0x7F
        value_start = offset + 2 + num_bytes
        length = int.from_bytes(data[offset + 2 : value_start], "big")
    else:
        length = data[offset + 1]
        value_start = offset + 2

    if length > len(data) - value_start:
        raise ValueError("Integer extends beyond buffer")

    value_bytes = data[value_start : value_start + length]

    if value_bytes and value_bytes[0] & 0x80:
        value = int.from_bytes(value_bytes, "big", signed=False)
    else:
        value = int.from_bytes(value_bytes, "big", signed=False)

    total_consumed = value_start + length - offset
    return value, total_consumed


def _parse_der_sequence(data: bytes, offset: int) -> Tuple[list[bytes], int]:
    """Parse a DER SEQUENCE and return (contents, bytes_consumed)."""
    if data[offset] != 0x30:
        raise ValueError(f"Expected SEQUENCE tag (0x30), got {data[offset]:02x}")

    length = data[offset + 1]
    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(data[offset + 2 : offset + 2 + num_bytes], "big")
        content_start = offset + 2 + num_bytes
    else:
        content_start = offset + 2

    if length > len(data) - content_start:
        raise ValueError("Sequence extends beyond buffer")

    return data[content_start : content_start + length], content_start + length - offset


def _parse_asn1_integer(data: bytes) -> int:
    """Parse an ASN.1 DER integer from raw data."""
    if not data:
        raise ValueError("Empty data")

    if data[0] != 0x02:
        raise ValueError(f"Expected INTEGER tag, got {data[0]:02x}")

    length = data[1]

    if length & 0x80:
        num_bytes = length & 0x7F
        length = int.from_bytes(data[2 : 2 + num_bytes], "big")
        value_start = 2 + num_bytes
    else:
        value_start = 2

    value_bytes = data[value_start : value_start + length]

    if value_bytes and value_bytes[0] & 0x80:
        return int.from_bytes(value_bytes, "big", signed=False)
    return int.from_bytes(value_bytes, "big", signed=False)


def parse_transformed_key(key_data: bytes) -> Tuple[int, int, int]:
    """Parse the transformed key file and return (n, e, transformed_d).

    The key file is a PKCS#1 DER structure with 9 integers:
    (version, n, e, transformed_d, 1, 1, 1, 1, 1).
    Only n, e, and transformed_d are meaningful.
    """
    if isinstance(key_data, str):
        key_data = key_data.encode("ascii")

    try:
        key_bytes = base64.b64decode(key_data)
    except Exception:
        key_bytes = key_data

    if len(key_bytes) < 4:
        raise ValueError("Key data too short")

    contents, _ = _parse_der_sequence(key_bytes, 0)

    # PKCS#1: skip version integer at position 0
    _, ver_consumed = _parse_der_integer(contents, 0)
    n, n_consumed = _parse_der_integer(contents, ver_consumed)
    e, e_consumed = _parse_der_integer(contents, ver_consumed + n_consumed)

    d_offset = ver_consumed + n_consumed + e_consumed
    transformed_d, _ = _parse_der_integer(contents, d_offset)

    return n, e, transformed_d


class CertificateHandler:
    """Handles GWM API certificates and key transformation."""

    def __init__(self, cert_dir: Path | None = None):
        if cert_dir is None:
            cert_dir = Path(__file__).parent.parent / "cert"
        self._cert_dir = cert_dir
        self._cert_with_key = None

    @property
    def certificate(self) -> x509.Certificate:
        """Load the client certificate."""
        cert_path = self._cert_dir / "gwm_general.cer"
        with open(cert_path, "rb") as f:
            data = f.read()
            if b"-----BEGIN" not in data:
                return x509.load_der_x509_certificate(data)
            return x509.load_pem_x509_certificate(data)

    @property
    def certificate_with_key(self) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Load the client certificate with private key."""
        if self._cert_with_key is not None:
            _LOGGER.debug("Returning cached certificate with key")
            return self._cert_with_key

        _LOGGER.info("Loading client certificate and key from: %s", self._cert_dir)
        cert = self.certificate
        key_path = self._cert_dir / "gwm_general.key"

        _LOGGER.info("Reading key file: %s", key_path)
        with open(key_path, "rb") as f:
            key_data = f.read()
        _LOGGER.info("Key file size: %d bytes", len(key_data))

        _LOGGER.info("Reconstructing RSA private key from transformed key data...")
        private_key = self._reconstruct_private_key(key_data)
        _LOGGER.info("RSA private key reconstruction successful")
        self._cert_with_key = (cert, private_key)
        return self._cert_with_key

    def _reconstruct_private_key(self, key_data: bytes) -> rsa.RSAPrivateKey:
        """Reconstruct RSA private key from transformed key data.

        Uses n and e from the certificate (the reliable source), and
        only extracts transformed_d from the key file.
        """
        cert = self.certificate
        pub_key = cert.public_key()
        pub_nums = pub_key.public_numbers()
        n = pub_nums.n
        e = pub_nums.e

        _LOGGER.debug("Using n=%d bits, e=%d from certificate", n.bit_length(), e)

        _LOGGER.debug("Parsing transformed key...")
        _, _, transformed_d = parse_transformed_key(key_data)

        n_bit_len = n.bit_length()
        _LOGGER.debug(
            "Parsed key: transformed_d=%d bits",
            transformed_d.bit_length(),
        )

        _LOGGER.debug("Running _untransform on d...")
        d = _untransform(transformed_d, n_bit_len)

        _LOGGER.debug("Recovering p and q via cryptography built-in...")
        p, q = rsa.rsa_recover_prime_factors(n, e, d)

        _LOGGER.debug("Computing CRT parameters...")
        dmp1 = rsa.rsa_crt_dmp1(d, p)
        dmq1 = rsa.rsa_crt_dmq1(d, q)
        iqmp = rsa.rsa_crt_iqmp(p, q)

        _LOGGER.debug("Building RSAPrivateNumbers...")
        pub_num = rsa.RSAPublicNumbers(e, n)
        priv_nums = rsa.RSAPrivateNumbers(p, q, d, dmp1, dmq1, iqmp, pub_num)

        return priv_nums.private_key()

    @property
    def chain(self) -> list[x509.Certificate]:
        """Load the CA chain certificate.

        Note: With cryptography >=46 the Rust ASN.1 parser rejects
        PrintableString encoding in GWM's old chain certs. Certs that
        fail to parse are skipped with a warning.
        """
        chain_path = self._cert_dir / "gwm_root.pem"
        with open(chain_path, "rb") as f:
            data = f.read()

        certs = []
        cert_data = []
        for line in data.split(b"\n"):
            if line.startswith(b"-----BEGIN"):
                cert_data = [line]
            elif line.startswith(b"-----END"):
                cert_data.append(line)
                try:
                    certs.append(x509.load_pem_x509_certificate(b"\n".join(cert_data)))
                except Exception:
                    _LOGGER.warning(
                        "Skipping chain cert that failed to parse (PrintableString encoding)"
                    )
                cert_data = []
            elif cert_data:
                cert_data.append(line)

        return certs

    def chain_intermediate_pem(self) -> bytes:
        """Return PEM bytes of intermediate (non-self-signed) CA certs.

        Uses pyOpenSSL to load the GWM chain certs and filter out the
        self-signed root, since cryptography >=46 rejects the old
        PrintableString encoding used in GWM's PEM files.
        """
        from OpenSSL import crypto as openssl_crypto

        chain_path = self._cert_dir / "gwm_root.pem"
        with open(chain_path, "rb") as f:
            data = f.read()

        result = bytearray()
        lines = data.split(b"\n")
        pem_lines = []
        for line in lines:
            if line.startswith(b"-----BEGIN"):
                pem_lines = [line]
            elif line.startswith(b"-----END"):
                pem_lines.append(line)
                pem = b"\n".join(pem_lines)
                try:
                    c = openssl_crypto.load_certificate(openssl_crypto.FILETYPE_PEM, pem)
                    subj = c.get_subject()
                    issr = c.get_issuer()
                    if subj.get_components() != issr.get_components():
                        result.extend(pem)
                        result.extend(b"\n")
                except Exception:
                    _LOGGER.warning("Failed to parse chain cert with pyOpenSSL")
                pem_lines = []
            elif pem_lines:
                pem_lines.append(line)

        return bytes(result)
