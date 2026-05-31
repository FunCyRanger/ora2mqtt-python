# GWM ORA

[![HACS Validation](https://github.com/FunCyRanger/ora2mqtt-python/actions/workflows/validate.yml/badge.svg)](https://github.com/FunCyRanger/ora2mqtt-python/actions/workflows/validate.yml)

> **⚠️ Disclaimer**: This project is **not affiliated with, endorsed by, or sponsored by GWM or ORA**. It is a community-maintained integration provided **as-is, without warranty of any kind**. Use at your own risk.

Home Assistant integration for GWM ORA vehicles (Funky Cat, etc.).

Based on the original [ora2mqtt](https://github.com/zivillian/ora2mqtt) by zivillian.

## Features

- **Sensors**: SOC, range, charging time, tire pressures & temperatures, odometer, interior temperature, and more
- **Binary sensors**: A/C status, lock, windows, charge plug, air circulation, defroster
- **Device tracker**: GPS location tracking
- **Auto token refresh**: Seamless token management with proactive refresh
- **Privacy-aware logging**: All sensitive data masked in logs
- **Configurable polling**: 10–300 second interval via options UI

## Installation

### Via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=FunCyRanger&repository=ora2mqtt-python&category=integration)

Or add manually:

1. Open Home Assistant → HACS → Integrations
2. Click the three-dot menu → **Add repository**
3. Enter `https://github.com/FunCyRanger/ora2mqtt-python`
4. Search for "GWM ORA" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/ora` directory to your HA `custom_components` folder
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "GWM ORA"
3. Enter your GWM ORA app email and password
4. If prompted, enter the verification code sent to your email
5. Adjust polling interval if desired (default: 60 s)

### Requirements

- Home Assistant 2026.1+
- [HACS](https://hacs.xyz) (recommended) or manual install
- A GWM ORA account

## Data Points

| Code | Sensor | Unit |
|------|--------|------|
| 2011501 | Range | km |
| 2013021 | SOC | % |
| 2013022 | Charging Time Remaining | min |
| 2013023 | SOC Target | % |
| 2041142 | Charging Active | — |
| 2041301 | SOCE | % |
| 2078020 | Air Circulation | — |
| 2101001–4 | Tire Pressure (FL/FR/RL/RR) | kPa |
| 2101005–8 | Tire Temperature (FL/FR/RL/RR) | °C |
| 2103010 | Odometer | km |
| 2201001 | Interior Temperature | °C |
| 2202001 | A/C | — |
| 2208001 | Lock | — |
| 2210001–4 | Windows (FL/FR/RL/RR) | — |
| 2222001 | Front Defroster | — |
| 2042082 | Charge Plug | — |

## Development

```bash
uv sync                          # Install dependencies
pytest                           # Run all tests
pytest -m integration            # Unit/integration tests
make lint                        # ruff check
make format                      # ruff format
```

See [API.md](API.md) for the GWM API reference and [DEV_NOTES.md](DEV_NOTES.md) for architectural notes.

## Contributing

Contributions welcome! Please open an issue or pull request on [GitHub](https://github.com/FunCyRanger/ora2mqtt-python).

## License

MIT
