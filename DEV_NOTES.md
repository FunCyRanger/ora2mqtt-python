# Developer Notes

---

## Specification: Current Workflows

### 1. Initial Login Flow (async_step_user)

```
┌─────────────────────────────────────┐
│  1. Show Login Form                 │
│     - Username (required)            │
│     - Password (required)            │
│     - [x] Request new code (default)│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. Submit Credentials               │
│     - Create fresh GwmApi           │
│     - Call login_with_email()        │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   Success          Error
       │               │
       ▼               ├─ 110641 → Email verification
       ▼               │   - Close API
   Create Entry      │   - Fresh API → get_email_code()
                     │   - Show email code form
                     │   - Store code_send_error for display
                     │
                     └─ Other → Show error on form

```

### 2. Re-authentication Flow (async_step_reauth)

```
┌─────────────────────────────────────┐
│  1. Show Re-auth Form               │
│     - Pre-filled email               │
│     - Password (required)            │
│     - [x] Request new code (default)│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. Submit Credentials               │
│     - Create/ensure GwmApi          │
│     - Retry up to 3 times            │
│       (2s → 4s → 8s backoff)         │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   Success          Error
       │               │
       ▼               ├─ 110641 → Email verification
   Update Entry      │   - Send code (if checkbox ON)
   + Abort            │   - Close API
                     │   - Show email code form
                     │   - Store code_send_error
                     │
                     ├─ 550002/308024 → Retry (transient)
                     │
                     └─ Other → Show error on form

```

### 3. Email Verification Flow (async_step_email_code)

```
┌─────────────────────────────────────┐
│  1. Show Email Code Form             │
│     - Error from code sending?       │
│       (e.g., 308024 rate limit)      │
│     - Show user-friendly message      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. User Submits Code                │
│     - Create fresh GwmApi             │
│     - Call verify_email_code()        │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   Success          Error
       │               │
       ▼               ▼
   Create/Update  Show error
   Entry + Close  + Abort (reauth)
   API            or Create Entry (login)
```

### 4. Token Refresh (Coordinator - Polling)

```
Every 60 seconds (default):
┌─────────────────────────────────────┐
│  1. Check token via get_user_info() │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   Valid           Error (570062)
       │               │
       ▼               ▼
   Fetch         Try refresh_token()
   vehicles           │
           ┌───────────┴───────────┐
           ▼                       ▼
       Success                  Fail (570062)
           │                       │
           ▼                       ▼
       Update tokens         ConfigEntryAuthFailed
       + Fetch vehicles      → HA triggers re-auth

```

---

## API Error Codes Reference

| Code | Description | Action |
|------|-------------|--------|
| 110641 | Email verification needed | Show email code form |
| 308024 | Rate limit - try later | Retry with backoff |
| 550002 | System busy | Retry with backoff |
| 570062 | Token expired | Trigger re-auth |

---

## Investigation: Why GWM API Returns "System busy" (550002)

### Problem
The Home Assistant integration gets "System busy, please try later" (error 550002) when the official GWM app works fine.

### Root Cause Analysis

#### 1. API Headers Comparison
Our integration vs Official App (from research):
| Header | Our Value | App Value |
|--------|-----------|-----------|
| rs | 2 | 2 |
| terminal | GW_APP_ORA | GW_APP_ORA |
| brand | 3 | 3 |
| language | en | en |
| systemType | 1 | 1 |
| cver | (empty) | 1.2.0 |

#### 2. Login Request Parameters Comparison
| Parameter | Our Value | App Value |
|-----------|-----------|-----------|
| model | ora2mqtt | P70 Pro (phone model) |
| deviceId | UUID | UUID (same) |
| appType | 0 | 0 |

### Changes Made

#### 1. Model Parameter (auth.py)
Changed from `"model": "ora2mqtt"` to `"model": "P70 Pro"` (realistic Android phone)

Locations changed:
- `login_with_email()` - line ~161
- `login_with_email()` with country param - line ~127
- `login_with_sms()` - line ~194

#### 2. App Version Header (client.py)
Changed `"cver": ""` to `"cver": "1.2.0"` (matches user's installed app version)

#### 3. Stable Device ID (config_flow.py)
Changed from random UUID to stable deterministic ID derived from HA config path.
- Old: `str(uuid.uuid4())` - random each time
- New: `_get_stable_device_id(hass)` - same for same HA instance

### Why These Changes Might Help

1. **Model parameter**: The API might be rate-limiting or blocking requests that identify as "ora2mqtt" (non-official client). Using a realistic phone model makes the request look more like the official app.

2. **App version (cver)**: The API might validate that the client version is supported. Empty or unknown versions might get lower priority or be rejected during busy periods.

3. **Stable device_id**: Email verification codes are linked to device_id. Random UUIDs caused verification failures because the device changed between code send and verification.

### Testing

After these changes:
1. Restart Home Assistant
2. Try re-authentication
3. Monitor logs for:
   - Successful login instead of "System busy"
   - Any new error patterns
   - Entity creation and data updates

### If Still Failing

Additional steps to try:
1. **Different phone model**: Try "iPhone 15" or "Pixel 7" instead
2. **Different app version**: Try "3.0.0" or "2.5.1"
3. **Network timing**: Add delay between retry attempts
4. **Capture actual traffic**: Use mitmproxy to capture real app traffic and compare exact headers/parameters

### References

- Original zivillian/ora2mqtt (C#): https://github.com/zivillian/ora2mqtt
- GWM Forum discussion: https://www.ora-funkycat-forum.de/forum/thread/915-meine-ora-funky-cat-app-api-basteleien/
- API documentation from reverse engineering available in zivillian repo

---

## Code Architecture Notes

### Authentication Flow

1. **Initial Login** (`async_step_user`):
   - User enters email + password + checkbox (default ON for new code)
   - API called: `login_with_email()`
   - If 110641 error → close API → fresh API → send code → show form
   - User enters code → fresh API → verify → create entry

2. **Email Verification** (`async_step_email_code`):
   - Code already sent (or not, based on checkbox) when form shows
   - User enters code → fresh API → verify → create/update entry

3. **Re-authentication** (`async_step_reauth`):
   - Triggered by HA when `ConfigEntryAuthFailed` raised
   - Retrieves config_entry from flow context
   - User enters credentials + checkbox (default ON)
   - Retries 3 times with exponential backoff (2s→4s→8s)
   - Transient errors: 550002 (System busy), 308024 (Rate limit)

4. **Token Refresh** (coordinator):
   - On every poll cycle, check token via `get_user_info()`
   - If 570062 → try `refresh_token()`
   - If refresh also fails → raise ConfigEntryAuthFailed

### Key Implementation Details

- **Config flow**: Methods must be in `ConfigFlow` class, NOT in `OptionsFlowHandler`
- **Empty user_input**: Use `if not user_input:` not `if user_input is None:` (HA may pass `{}`)
- **Coordinator polling**: Uses DataUpdateCoordinator's built-in polling (no manual start/stop)
- **Retry logic**: Both coordinator and config flow have retry for transient errors
- **Fresh API instances**: Each API call creates new GwmApi instance (previous was closed)
- **Stable device_id**: Generated from HA config path, not random UUID

### Polling & Retry Constants

```python
# Coordinator (polling)
DEFAULT_POLL_INTERVAL = 60  # seconds
RETRY_BASE_DELAY = 10  # seconds
RETRY_MAX_DELAY = 120  # seconds (> poll interval)
RETRY_MAX_ATTEMPTS = 3

# Config flow (re-auth)
RETRY_BASE_DELAY = 2  # seconds (shorter for UI responsiveness)
RETRY_MAX_ATTEMPTS = 3

# Transient errors that trigger retry
TRANSIENT_ERRORS = {"550002", "308024"}  # System busy, Rate limit
```

### Device ID Generation

```python
def _get_stable_device_id(hass: HomeAssistant, entry_id: str | None = None) -> str:
    """Generate a stable device ID for this HA instance.

    Uses a deterministic UUID based on the HA config directory path.
    This ensures the same HA instance always gets the same device_id,
    which is important for email verification and token management.
    """
    namespace = uuid.NAMESPACE_DNS
    name = hass.config.path()
    if entry_id:
        name = f"{name}:{entry_id}"
    return str(uuid.uuid5(namespace, name))
```

### Comparison: Python vs Old C# Implementation

| Area | Python Implementation | Old C# Implementation | Status |
|------|------------------------|------------------------|--------|
| Token refresh | get_user_info() → refresh_token() | Direct refresh_token() | ✅ Better |
| Poll interval | 60 seconds | 60 seconds | ✅ Match |
| Device ID | Stable from config path | Persistent config file | ✅ Similar |
| Headers | Matches app (cver=1.2.0) | Matches app | ✅ Match |
| Payload | Matches app (model=P70 Pro) | Matches app | ✅ Match |