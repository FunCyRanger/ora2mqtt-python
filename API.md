# GWM ORA API Reference

This document describes the GWM ORA vehicle API used by this Home Assistant integration. It covers authentication, token management, vehicle data retrieval, and remote control commands.

## Architecture

The integration communicates with two GWM gateways:

| Gateway | Host | Purpose | Auth | TLS |
|---------|------|---------|------|-----|
| h5-gateway | `eu-h5-gateway.gwmcloud.com` | Authentication, token operations | Plain HTTPS | Server-only |
| app-gateway | `eu-app-gateway.gwmcloud.com` | Vehicle data, status, remote control | mTLS (client cert) | Mutual |

All endpoints use the prefix `/app-api/api/v1.0/`.

### Base Headers (all requests)

```
rs: 2
terminal: GW_APP_ORA
brand: 3
language: en
systemType: 1
cver: 1.2.0
country: <country_code>      # e.g. DE
accessToken: <token>         # app-gateway requests only
```

---

## Authentication

### Primary Login: Email + Password

**Endpoint**: `POST /app-api/api/v1.0/userAuth/loginAccount`
**Gateway**: h5-gateway (plain HTTPS)
**Token**: No (public endpoint)

**Request**:
```json
{
  "account": "<email>",
  "password": "<password>",
  "deviceId": "<device_id>",
  "country": "DE",
  "appType": 0,
  "model": "P70 Pro",
  "agreement": [1, 2, 23],
  "isEncrypt": false,
  "pushToken": "",
  "type": 1
}
```

**Response** (success, code `000000`):
```json
{
  "code": "000000",
  "description": "SUCCESS",
  "data": {
    "accessToken": "eyJhbGciOiJSUzI1NiJ9...",
    "refreshToken": "eyJhbGciOiJSUzI1NiJ9...",
    "expiresIn": 86400,
    "userId": "user_123456789",
    "gwId": "gw_123456789",
    "beanId": "bean_1234567890",
    "email": "u..13..l"
  }
}
```

**Response** (untrusted device, code `110641`):
```json
{
  "code": "110641",
  "description": "login via untrusted device, verification code is needed"
}
```

On `110641`, fall back to email verification code flow.

---

### Email Verification Code (untrusted device)

#### Step 1: Request code

**Endpoint**: `POST /app-api/api/v1.0/userAuth/getSMSCode`
**Gateway**: h5-gateway
**Token**: No

```json
{
  "email": "<email>",
  "scenario": 0,
  "type": 3
}
```

#### Step 2: Submit code

**Endpoint**: `POST /app-api/api/v1.0/userAuth/loginWithSMS`
**Gateway**: h5-gateway
**Token**: No

```json
{
  "email": "<email>",
  "smsCode": "<code>",
  "deviceId": "<device_id>",
  "country": "DE",
  "model": "P70 Pro",
  "agreement": [1, 2, 23],
  "appType": 0
}
```

**Response** (success):
```json
{
  "code": "000000",
  "data": {
    "accessToken": "eyJhbGciOiJSUzI1NiJ9...",
    "refreshToken": "eyJhbGciOiJSUzI1NiJ9...",
    "expiresIn": 86400,
    "userId": "user_123456789",
    "gwId": "gw_123456789",
    "beanId": "bean_1234567890",
    "email": "u..13..l"
  }
}
```

**Response** (refresh token expired):
```json
{
  "code": "570062",
  "description": "Refresh Token has expired"
}
```

On `570062`, the integration triggers re-authentication via Home Assistant's config flow.

---

## Vehicle Data

### List Vehicles

**Endpoint**: `GET /app-api/api/v1.0/globalapp/vehicle/acquireVehicles`
**Gateway**: app-gateway (mTLS required)
**Token**: Yes (accessToken header)

**Response**:
```json
{
  "code": "000000",
  "data": [
    {
      "vin": "LHG12345678901234",
      "brandName": "ORA",
      "appShowSeriesName": "GWM ORA 03",
      "vtype": "FUNKY CAT",
      "deviceId": "L..15..7",
      "modelCode": "ORA FUNKY CAT_CC7000BJ04BBEV_2022_CHIC",
      "salesMarket": "DE",
      "shareId": "30475",
      "engineNo": "Q..5..1",
      "vehicleId": "6..60..4",
      "imsi": "2..13..6"
    }
  ]
}
```

---

### Vehicle Status

**Endpoint**: `GET /app-api/api/v1.0/vehicle/getLastStatus?vin=<vin>&seqNo=`
**Gateway**: app-gateway (mTLS required)
**Token**: Yes

**Response**:
```json
{
  "code": "000000",
  "data": {
    "acquisitionTime": 1778083544000,
    "updateTime": 1778083546435,
    "deviceId": "L..15..7",
    "latitude": "52.52",
    "longitude": "13.40",
    "items": [
      {"code": "2013021", "value": 77, "unit": "%"},
      {"code": "2011501", "value": "330", "unit": "Km"},
      {"code": "2103010", "value": 13119, "unit": "Km"},
      {"code": "2202001", "value": 1, "unit": "°C"},
      {"code": "2208001", "value": "0", "unit": null},
      {"code": "2210001", "value": "1", "unit": null},
      {"code": "2041142", "value": "0", "unit": null},
      {"code": "2042082", "value": "0", "unit": null}
    ]
  }
}
```

### Status Item Codes

| Code | Name | Unit | Description |
|------|------|------|-------------|
| 2011501 | range | km | Remaining range |
| 2013021 | soc | % | State of Charge |
| 2013022 | charging_time_remaining | min | Charging time left |
| 2013023 | soc_target | % | SOC target |
| 2041142 | charging_active | - | Charging active (0/1) |
| 2041301 | soce | % | SOC estimated |
| 2078020 | air_circulation | - | Air circulation (0/1) |
| 2101001–2101004 | tire_pressure_fl/fr/rl/rr | kPa | Tire pressures |
| 2101005–2101008 | tire_temp_fl/fr/rl/rr | °C | Tire temperatures |
| 2102001–2102004 | window_fl/fr/rl/rr | - | Window position (3=open, 1=closed) |
| 2103010 | odometer | km | Total distance |
| 2201001 | interior_temp | °C | Interior temperature |
| 2202001 | ac | - | A/C on (0/1) |
| 2208001 | lock | - | Lock status (0=unlocked, 1=locked) |
| 2210001–2210004 | window_fl/fr/rl/rr | - | Windows (3=open, 1=closed) |
| 2222001 | defroster_front | - | Front defroster (0/1) |
| 2042082 | charge_plug | - | Charge plug connected (0/1) |

---

## Remote Control

### Send Command (T5)

**Endpoint**: `POST /app-api/api/v1.0/vehicle/T5/sendCmd`
**Gateway**: app-gateway (mTLS)
**Token**: Yes

```json
{
  "vin": "LHG12345678901234",
  "command": "unlock"
}
```

**Response**:
```json
{
  "code": "000000",
  "data": {
    "seqNo": "T5SEQ12345"
  }
}
```

### Get Command Result

**Endpoint**: `GET /app-api/api/v1.0/vehicle/getRemoteCtrlResultT5?seqNo=<seq_no>`
**Gateway**: app-gateway (mTLS)
**Token**: Yes

**Response**:
```json
{
  "code": "000000",
  "data": [
    {
      "seqNo": "T5SEQ12345",
      "result": "success",
      "resultCode": "0",
      "message": "Command executed successfully"
    }
  ]
}
```

---

## Error Codes

| Code | Name | Behavior |
|------|------|---------|
| `000000` | SUCCESS | Operation succeeded |
| `110641` | Untrusted device | Email verification required (fallback to `loginWithSMS`) |
| `550004` | Login Token expired | Attempt token refresh, then re-auth if refresh fails |
| `570062` | Refresh Token expired | Trigger full re-authentication |
| `308024` | Rate limit | Retry with exponential backoff (10s→20s→40s, max 120s) |
| `550002` | System busy | Not transient — do not retry, raise error |

---

## Token Lifecycle

```
Login (email + password)
    ↓
access_token + refresh_token + expires_in stored in HA config entry
    ↓
On each poll cycle:
    ├─ Proactive refresh: if token_issued_at + expires_in - 5min < now → refresh()
    ├─ Vehicle API call with access_token
    │   ├─ 550004/570062 → refresh_token() → retry
    │   └─ refresh fails → ConfigEntryAuthFailed → HA re-auth flow
    └─ All good → vehicle data returned to HA
```

### Important Notes

- **Setting `country` clears `accessToken`** — the `GwmHttpClient.country` setter resets the token to `None` as a side effect. Initialize country before setting the token.
- **`expires_in=0`** is a valid API response. It means the token is already "expired" by API definition, but the token may still work for some time. The integration treats this as "skip proactive refresh."
- **Device ID** is a stable UUID5 derived from the Home Assistant config path. It is deterministic per HA install and survives restarts.
- **No `get_user_info()` on every poll** — removed in v0.2.35. Token validity is determined reactively from vehicle API responses (`550004` / `570062`).

---

## Certificate Authentication (mTLS)

The vehicle API (`app-gateway`) requires mutual TLS authentication. The integration includes bundled certificates:

| File | Purpose |
|------|---------|
| `gwm_general.cer` | Client certificate (public key + identity) |
| `gwm_general.key` | Private key (transformed, not standard PEM) |
| `gwm_root.pem` | CA certificate chain (2 intermediate certs + 1 root) |

The private key uses a custom transformation encoding (5-bit chunk LSB→MSB) to reconstruct the RSA key. The key is bundled in the integration and used for the TLS handshake with GWM's servers. The same client certificate identity is used for all installations.

The CA chain includes intermediate certificates that use SHA-1 signatures, which requires `SECLEVEL=0` in the TLS context (OpenSSL 3.x workaround). The root CA is excluded from the handshake; only the two intermediate certificates are sent alongside the client cert.

---

## Configuration Flow

```
User enters email + password
    ↓
loginAccount() → 110641?
    ├─ No → tokens stored → polling starts
    └─ Yes → get_email_code() → user enters code
              ↓
         verify_email_code() → tokens stored → polling starts
```

On token expiry during polling:

```
Vehicle API returns 550004 / 570062
    ↓
refreshToken() → success?
    ├─ Yes → retry vehicle API
    └─ No (570062) → ConfigEntryAuthFailed → HA re-auth config flow
                       ↓
                  loginAccount() → 110641?
                       ├─ No → tokens updated → polling resumes
                       └─ Yes → email code flow → tokens updated → polling resumes
```