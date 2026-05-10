# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.2] - 2026-05-10

### Added

- **Device grouping in Home Assistant UI**: All entities (sensors, binary sensors, device tracker) now set `_attr_device_info` with GWM manufacturer, vehicle name, model, and VIN as identifier. Entities are properly grouped under a single Device card in HA.
- **New device_info tests**: Added 35 tests covering device_info on all entity types, consistency checks across sensors/binary sensors/tracker for the same VIN, and vehicle name reflection.

### Fixed

- **window_rr unit**: Fixed `°C` → `None` in DATA_POINTS (was incorrectly set for a binary sensor).

### Changed

- Thread `vehicle` object through entity factory functions for access to vehicle metadata.

---

## [1.0.0] - 2026-05-10

### Added

- **Privacy-aware logging**: All privacy-sensitive data (emails, VINs, tokens, GPS coordinates, engine numbers, SIM identifiers) is now masked in logs with `X..N..X` format (first/last char kept, middle abbreviated). Covers all log statements across config flow, coordinator, auth, vehicles, and HTTP client.
- **Proactive token refresh**: Token is automatically refreshed before expiration (5-minute buffer). Prevents mid-poll token expiry interruptions.
- **Re-auth flow**: Automatic re-authentication when tokens expire, with email verification code fallback.
- **Comprehensive structured logging**: All API calls, token operations, and config flow steps are logged for debugging.

### Changed

- **Refresh loop fix**: Coordinator no longer gets stuck in a re-auth loop when `expires_in=0` (API may return this on initial token setup). Proactive refresh is now skipped for invalid expiry values.
- **mTLS certificate chain**: Fixed intermediate CA chain injection in mTLS handshake. Server now accepts client certificates. Added SECLEVEL=0 workaround for SHA-1 intermediate cert compatibility.

### Fixed

- Handle `550004` token expired alongside `570062` in coordinator
- Stop `550002` retry loop (system busy, not transient)
- Fix double-reload crash in update listener
- Use stable device ID from HA config path (deterministic, survives restarts)
- Country setter no longer clears access token on startup
- `get_user_info()` removed — was causing unnecessary h5-gateway pings on every poll cycle

### Security

- Privacy sanitization in all logging paths
- RSA key reconstruction from transformed private key (bundled cert)
- mTLS client certificate authentication

---

## [0.2.x] - 0.2.49

See git history for details.

### Key fixes

- mTLS SSL context caching bug (h5-gateway requests could use app-gateway context)
- RSA key reconstruction from transformed key data
- Correct SECLEVEL handling for intermediate CA chain
- Vehicle API `570062` token refresh alongside `550004`
- Re-auth config flow with email code verification

---

## [0.1.0] - Initial beta

- Initial Python rewrite from C# ora2mqtt (by zivillian)
- Email + password authentication with SMS code fallback
- Config flow setup via Home Assistant UI
- Sensors, binary sensors, device tracker
- Token refresh mechanism
- mTLS client certificate support