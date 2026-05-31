# AGENTS.md

The HACS validation + hassfest CI workflow is at `.github/workflows/validate.yml`. It runs on push, PR, and daily schedule.

## Dev Commands

```bash
uv sync               # Install deps (uv.lock is source of truth)
pytest                # All tests
pytest -m integration # No HA runtime needed
pytest -m system      # Requires HA runtime (pytest-homeassistant-custom-component)
pytest --cov          # Coverage
make lint             # ruff check custom_components/ora tests
make format           # ruff format custom_components/ora tests
make test-cov         # pytest --cov=custom_components.ora with HTML report
make test-integration # pytest -m integration
make test-system      # pytest -m system
make clean            # Remove __pycache__, .coverage, htmlcov
```

Style: Python >=3.14 (pyproject.toml), ruff double quotes, line-length 100 (ruff.toml), pytest asyncio_mode=auto.

## Architecture

- `custom_components/ora/` — HA custom component (entry point: `async_setup_entry` in `__init__.py`). Manifest `iot_class: cloud_polling`, depends on `mqtt`.
- `custom_components/ora/api/` — API subpackage; `GwmApi` facade composes `GwmHttpClient` + `GwmAuthClient` + `GwmVehicleClient`
- `custom_components/ora/cert/` — mTLS certificates. The bundled private key (`gwm_general.key`) is a **transformed** PKCS#1 DER; `cert.py` reconstructs it via inverse chunk encoding + `rsa.rsa_recover_prime_factors`.
- `tests/integration/` — Unit/integration tests (no HA runtime)
- `tests/system/` — Full HA integration tests (needs `pytest-homeassistant-custom-component`)

### API Endpoints

Two gateway URLs, selected via `use_app_gateway` flag on `GwmHttpClient`:
- **h5_gateway** (`eu-h5-gateway.gwmcloud.com`): auth/login/email-code (no mTLS)
- **app_gateway** (`eu-app-gateway.gwmcloud.com`): vehicles/status (requires mTLS)

Setting `country` on the client **clears** the access token (`client.py:68-70`).

## Config Flow

Three steps in `ConfigFlow` class (NOT in `OptionsFlowHandler`):
- `async_step_user` — email/password login
- `async_step_email_code` — email verification (API code `110641` triggers this)
- `async_step_reauth` — triggered by `ConfigEntryAuthFailed`, retries 3× (2s→4s→8s), only retries `308024` (not `550002`)
- Options flow (`OptionsFlowHandler.async_step_init`) handles poll interval (10-300s) and manual re-auth trigger

Critical patterns:
- `if not user_input:` not `if user_input is None:` — HA may pass `{}`.
- **Fresh API instances**: config flow creates new `GwmApi()` for each step after `close()` on previous.
- **Stable device_id** from `_get_stable_device_id(hass)` via uuid5 of `hass.config.path()`.
- **Update listener** (`_async_entry_updated_listener` in `__init__.py`) updates coordinator **in-place** — no full reload. Avoids re-entrant loops when `async_update_entry` triggers the listener during setup.

## Token Management

- **Proactive refresh**: coordinator checks `token_issued_at` + `expires_in` before each poll cycle; refreshes if ≤5 min from expiry
- **On-demand refresh**: if vehicle API returns `570062` or `550004`, calls `_do_token_refresh()`. Non-matching API errors propagate as `GwmApiException` (not retried). HTTP errors (502, timeouts) retried 3× with backoff in `_fetch_vehicle_data_with_retry`.
- **Both fail**: raises `ConfigEntryAuthFailed` → triggers HA re-auth flow
- **No `get_user_info()` call** on poll (removed v0.2.35). Token validity determined reactively via vehicle API responses.

## Polling & Retry (Coordinator)

- Default interval: 60s (configurable 10-300s)
- Transient errors (`308024` rate limit): retry 10s→20s→40s (max 120s, 3 attempts)
- `DataUpdateCoordinator` built-in polling (no manual start/stop)
- `550002` ("System busy") treated as `UpdateFailed`, NOT retried

## Sensors

Platforms: `[Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]`

Data points in `const.py` (`DATA_POINTS` keyed by API code). Sensors added via listener pattern — `async_add_listener` in `sensor.py` adds entities when coordinator first has data, not at setup time.

## Testing

- **Markers required**: `@pytest.mark.integration` and `@pytest.mark.system`
- **Autouse fixtures** (`conftest.py`): `mock_ora_integration` (patches HA loader), `patch_certificates`, `prevent_entry_setup` (avoids HA setup post-config-flow)
- **Fixtures**: `tests/fixtures/api_responses.py` (mock API responses), `tests/fixtures/certificates.py` (mock cert PEMs)
- **Mocking**: `AsyncMock` on `GwmHttpClient._request` — aioresponses not used

## Common Pitfalls

- **Config flow methods in `ConfigFlow`**: `async_step_user`, `async_step_email_code`, `async_step_reauth`, `_create_entry` must be in `ConfigFlow`, NOT `OptionsFlowHandler`. HA shows "not_implemented" otherwise.
- **Check user_input with `if not user_input:`** — HA may pass empty dict `{}` not `None`.
- **Private key is non-standard**: `gwm_general.key` is a 9-integer PKCS#1 DER with a transformed `d` via 5-bit chunk encoding. `CertificateHandler._reconstruct_private_key` in `cert.py` handles the full decode.
- **Country setter clears token**: `GwmHttpClient.country` setter resets `_access_token` to `None`.
- **Email code endpoint**: `get_email_code()` and `send_email_code()` both hit `userAuth/getSMSCode` with different `scenario` values.
- **SSL context caching**: Two separate caches — `_ssl_context` (plain, h5-gateway) and `_ssl_context_client` (mTLS, app-gateway). Always check `require_client_cert` before returning cached context. Single-cache design broke app-gateway requests.
- **mTLS intermediate CA chain**: `gwm_root.pem` intermediates must be concatenated with the client cert in `load_cert_chain` (exclude the self-signed root). Without them, server returns HTTP 400.
- **SHA-1 intermediate + OpenSSL 3**: `IOV APP General SubCA` uses SHA-1; OpenSSL 3.x rejects at default seclevel 2. Workaround: set `@SECLEVEL=0` for the mTLS context, use `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` (not `create_default_context`).
- **cryptography >=46 chain parsing**: GWM's `gwm_root.pem` uses old PrintableString encoding that the Rust ASN.1 parser rejects. Use `chain_intermediate_pem()` (pyOpenSSL) instead of `chain` property.
