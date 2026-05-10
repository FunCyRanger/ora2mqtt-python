# AGENTS.md

## Dev Commands

```bash
uv sync               # Install deps (uv.lock is source of truth)
pytest                # All tests
pytest -m integration # No HA runtime needed
pytest -m system      # Requires HA runtime (pytest-homeassistant-custom-component)
pytest --cov          # Coverage
make lint             # ruff check custom_components/ora tests
make format           # ruff format custom_components/ora tests
make test-cov         # pytest --cov with HTML report
make clean            # Remove __pycache__, .coverage, htmlcov
```

Style: Python 3.12+, ruff double quotes, line-length 100 (ruff.toml), pytest asyncio_mode=auto.

## Architecture

- `custom_components/ora/` — HA custom component (entry point: `async_setup_entry` in `__init__.py`)
- `custom_components/ora/api/` — API subpackage; `GwmApi` facade composes `GwmHttpClient` + `GwmAuthClient` + `GwmVehicleClient`
- `custom_components/ora/cert/` — mTLS certificates (gwm_general.cer/key, gwm_root.pem). The private key is **transformed**; RSA is reconstructed via `cert.py` (`parse_transformed_key` → `_untransform` → `rsa.rsa_recover_prime_factors`)
- `tests/integration/` — Unit/integration tests (no HA runtime)
- `tests/system/` — Full HA integration tests

### API Endpoints

Two gateway URLs, selected via `use_app_gateway` flag on `GwmHttpClient`:
- **h5_gateway** (`eu-h5-gateway.gwmcloud.com`): auth/login/email-code (no mTLS)
- **app_gateway** (`eu-app-gateway.gwmcloud.com`): vehicles/status (requires mTLS)

Setting `country` on the client **clears** the access token (`client.py:78`).

## Config Flow

Three steps in `ConfigFlow` class (NOT in `OptionsFlowHandler`):
- `async_step_user` — email/password login
- `async_step_email_code` — email verification (code 110641 triggers this)
- `async_step_reauth` — triggered by `ConfigEntryAuthFailed`, retries 3× (2s→4s→8s), only retries `308024` (not `550002`)
- Options flow (`OptionsFlowHandler.async_step_init`) handles poll interval and manual re-auth trigger

Critical pattern: `if not user_input:` not `if user_input is None:` — HA may pass `{}`.

**Fresh API instances**: config flow creates new `GwmApi()` for each step after `close()` on previous. Stable `device_id` from `_get_stable_device_id(hass)` via `hass.config.path()` (uuid5, deterministic).

**Update listener** (`_async_entry_updated_listener` in `__init__.py`) updates coordinator **in-place** — no full reload. Avoids re-entrant reload loops when `async_update_entry` triggers the listener during setup.

## Token Management

- **Proactive refresh**: coordinator checks `token_issued_at` + `expires_in` before each poll cycle; refreshes if ≤5 min from expiry
- **On-demand refresh**: if vehicle API returns `570062` or `550004`, calls `_do_token_refresh()`. Non-matching API errors propagate as `GwmApiException` (not retried). HTTP errors (502, timeouts) are retried 3× with backoff within `_fetch_vehicle_data_with_retry`.
- **Both fail**: raises `ConfigEntryAuthFailed` → triggers HA re-auth flow
- **No `get_user_info()` call**: removed in v0.2.35 — no longer pings the unreliable h5-gateway `userBaseInfo` endpoint on every poll cycle. Token validity is determined reactively via vehicle API responses.

## Polling & Retry (Coordinator)

- Default interval: 60s (configurable 10-300s via options)
- Transient errors (`308024` rate limit): retry 10s→20s→40s (max 120s, 3 attempts)
- `DataUpdateCoordinator` built-in polling (no manual start/stop needed)
- `550002` ("System busy") is NOT retried in coordinator (treated as `UpdateFailed`)

## Sensors

Platforms: `[Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]`

Data points defined in `const.py` (dict `DATA_POINTS` keyed by API code). Sensors created via listener pattern — `async_add_listener` in `sensor.py` adds entities when coordinator first has data, not during setup.

## Testing

- **Markers required**: `@pytest.mark.integration` and `@pytest.mark.system`
- **Autouse fixtures**: `mock_ora_integration` (patches HA loader), `patch_certificates`, `prevent_entry_setup` (avoids HA setup post-config-flow)
- **Fixtures**: `tests/fixtures/api_responses.py` has mock API responses; `tests/fixtures/certificates.py` has mock cert PEMs
- **aioresponses**: not used — tests mock via `AsyncMock` on `GwmHttpClient._request`

## Common Pitfalls

- **Config flow methods in `ConfigFlow`**: `async_step_user`, `async_step_email_code`, `async_step_reauth`, `_create_entry` must be in `ConfigFlow`, NOT `OptionsFlowHandler`. HA shows "not_implemented" otherwise.
- **Empty user_input**: Use `if not user_input:` to catch both `None` and `{}`.
- **Private key transformation**: The bundled `gwm_general.key` is NOT a standard PEM — it's a 9-integer PKCS#1 DER SEQUENCE (version, n, e, transformed_d, 1, 1, 1, 1, 1). `parse_transformed_key` skips the version integer and reads n/e/transformed_d at positions 1/2/3. n and e are also sourced from the certificate via `public_key()`. `_untransform` reverses the 5-bit chunk encoding: chunks are extracted LSB-first, reversed to MSB-first, the MSB chunk is taken raw, then each remaining chunk has `g(v) = (v & 0xF8) + ((v + 3) & 7)` applied (inverse of the server's `h(v) = (v & 0xF8) | (((v & 7) - 3) & 7)`). `rsa.rsa_recover_prime_factors` recovers p/q, and CRT parameters are computed via cryptography built-ins.
- **Country setter clears token**: `GwmHttpClient.country` setter resets `_access_token` to `None`.
- **Email code sends**: `get_email_code()` and `send_email_code()` call the same endpoint `userAuth/getSMSCode` with different `scenario` values. Both exist in `auth.py`.
- **SSL context caching**: Two separate cached contexts — `_ssl_context` (plain, h5-gateway) and `_ssl_context_client` (mTLS, app-gateway). The original single-cache design caused app-gateway requests to use the non-mTLS context if an h5-gateway request created it first. Always check `require_client_cert` before returning a cached context.
- **Intermediate CA chain for mTLS**: The `gwm_root.pem` chain must be concatenated with the client cert in `load_cert_chain`. The GWM leaf cert is issued by `IOV APP General SubCA` which is signed by `GWM Root CA`. Both intermediates (SHA-256 `emailAddress=cybersecurity@gwm.cn` and SHA-1 `IOV APP General SubCA`) are included; the root (self-signed `GWM Root CA`) is excluded. Without intermediates, the server returns HTTP 400 — matching the original C# ora2mqtt behavior which injects them into the Windows CA store.
- **SHA-1 intermediate cert**: `IOV APP General SubCA` uses `sha1WithRSAEncryption` which OpenSSL 3.x rejects at default security level 2 during `load_cert_chain`. Workaround: permanently set `@SECLEVEL=0` for the mTLS context (the server's GlobalSign root CA also uses SHA-1 for its self-signature). `ssl.create_default_context()` must be replaced with `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` to control this.
- **cryptography >=46 chain parsing**: GWM's `gwm_root.pem` uses old PrintableString encoding in certificate subjects/issuers. The Rust ASN.1 parser in cryptography 46.x rejects this. The `chain` property skips unparseable certs with a warning. Use `chain_intermediate_pem()` instead, which uses pyOpenSSL (uses system OpenSSL backend, more lenient).
