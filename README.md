# GWM ORA Integration for Home Assistant

A native Home Assistant integration for GWM ORA vehicles (Funky Cat, etc.).

Based on the original work by [zivillian](https://github.com/zivillian/ora2mqtt). Thank you for the excellent foundation!

## Features

- **Sensors**: SOC (State of Charge), Range, SOCE, Odometer, Tire pressures (4x), Tire temperatures (4x), Interior temperature, Acquisition time
- **Binary Sensors**: A/C, Lock, Windows (4x), Charge plug, Air circulation, Front defroster
- **Device Tracker**: GPS location
- **Privacy-aware logging**: All sensitive data is masked in logs
- **Auto-refresh**: Automatic token refresh before expiration
- **Config Flow**: Easy setup via Home Assistant UI
- **mTLS Authentication**: Client certificate for secure vehicle API communication

## Installation

### Via HACS (Recommended)

1. Open Home Assistant
2. Go to HACS > Integrations
3. Click the three dots menu > Add repository
4. Enter: `https://github.com/FunCyRanger/ora2mqtt-python`
5. Search for "GWM ORA" and install
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ora` folder to your Home Assistant's `custom_components` folder
2. Restart Home Assistant

## Configuration

1. Go to Settings > Devices & Services > Add Integration
2. Search for "GWM ORA"
3. Enter your GWM/ORA app email address and password
4. If verification is required, enter the SMS code sent to your email/phone
5. Configure polling interval (default: 60 seconds)

### Authentication

The integration uses the same authentication mechanism as the official GWM/ORA app:

1. **Primary Login**: Email + password authentication to the `eu-h5-gateway.gwmcloud.com` API
2. **Client Certificate**: Bundled client certificate (`gwm_general.cer/key`) is used for secure mTLS communication with the vehicle API (`eu-app-gateway.gwmcloud.com`)
3. **SMS Verification (Fallback)**: If the account requires additional verification (error code 110641), an SMS/code is sent to your registered email/phone

The client certificate enables mutual TLS (mTLS) authentication required by the vehicle API endpoint, ensuring secure communication between your Home Assistant instance and GWM's servers.

## Supported Regions

- EU (default)

## Certificates

The integration includes bundled certificates for secure communication:

- `gwm_general.cer` - Client certificate
- `gwm_general.key` - Private key (RSA with transformation)
- `gwm_root.pem` - CA certificate chain

These certificates enable mutual TLS (mTLS) authentication with the GWM vehicle API endpoint.

## Data Points

| Code | Description |
|------|-------------|
| 2011501 | Range (km) |
| 2013021 | SOC (%) |
| 2013022 | Charging time remaining (min) |
| 2013023 | SOC target (%) |
| 2041142 | Charging active |
| 2041301 | SOCE (%) |
| 2078020 | Air circulation |
| 2101001 | Tire pressure FL (kPa) |
| 2101002 | Tire pressure FR (kPa) |
| 2101003 | Tire pressure RL (kPa) |
| 2101004 | Tire pressure RR (kPa) |
| 2101005 | Tire temperature FL (°C) |
| 2101006 | Tire temperature FR (°C) |
| 2101007 | Tire temperature RL (°C) |
| 2101008 | Tire temperature RR (°C) |
| 2103010 | Odometer (km) |
| 2201001 | Interior temperature (°C) |
| 2202001 | A/C |
| 2208001 | Lock |
| 2210001 | Window FL |
| 2210002 | Window FR |
| 2210003 | Window RL |
| 2210004 | Window RR |
| 2222001 | Front defroster |
| 2042082 | Charge plug |

## Requirements

- Home Assistant 2026.1+
- Python 3.12+

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Format code
ruff format

# Lint
ruff check
```

## API Reference

See [API.md](API.md) for detailed documentation of the GWM ORA API endpoints, authentication flow, token lifecycle, and error codes.

## License

MIT