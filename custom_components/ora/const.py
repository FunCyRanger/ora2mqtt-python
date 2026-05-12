"""Constants for GWM ORA integration."""

DOMAIN = "ora"

# Data point codes from GWM API
DATA_POINTS = {
    2011501: ("range", "km", "Range"),
    2013021: ("soc", "%", "SOC"),
    2013022: ("charging_time_remaining", "min", "Charging Time Remaining"),
    2013023: ("soc_target", "%", "SOC Target"),
    2041142: ("charging_active", None, "Charging Active"),
    2041301: ("soce", "%", "SOCE"),
    2078020: ("air_circulation", None, "Air Circulation"),
    2101001: ("tire_pressure_fl", "kPa", "Tire Pressure FL"),
    2101002: ("tire_pressure_fr", "kPa", "Tire Pressure FR"),
    2101003: ("tire_pressure_rl", "kPa", "Tire Pressure RL"),
    2101004: ("tire_pressure_rr", "kPa", "Tire Pressure RR"),
    2101005: ("tire_temp_fl", "°C", "Tire Temperature FL"),
    2101006: ("tire_temp_fr", "°C", "Tire Temperature FR"),
    2101007: ("tire_temp_rl", "°C", "Tire Temperature RL"),
    2101008: ("tire_temp_rr", "°C", "Tire Temperature RR"),
    2103010: ("odometer", "km", "Odometer"),
    2201001: ("interior_temp", "°C", "Interior Temperature"),
    2202001: ("ac", None, "A/C"),
    2208001: ("lock", None, "Lock"),
    2210001: ("window_fl", None, "Window FL"),
    2210002: ("window_fr", None, "Window FR"),
    2210003: ("window_rl", None, "Window RL"),
    2210004: ("window_rr", None, "Window RR"),
    2222001: ("defroster_front", None, "Front Defroster"),
    2042082: ("charge_plug", None, "Charge Plug"),
}

# Binary sensor mappings (code: (attribute, device_class, payload_on, payload_off))
BINARY_SENSORS = {
    2202001: ("ac", "running", "1", "0"),
    2208001: ("lock", "lock", "1", "0"),
    2210001: ("window_fl", "window", "3", "1"),
    2210002: ("window_fr", "window", "3", "1"),
    2210003: ("window_rl", "window", "3", "1"),
    2210004: ("window_rr", "window", "3", "1"),
    2078020: ("air_circulation", "running", "1", "0"),
    2222001: ("defroster_front", "heat", "1", "0"),
    2042082: ("charge_plug", "plug", "1", "0"),
    2041142: ("charging_active", "heat", "1", "0"),
}

DEFAULT_POLL_INTERVAL = 60

CONF_ACCOUNT = "account"
CONF_ACCOUNT_COUNTRY = "country"
CONF_ACCOUNT_EMAIL = "email"
CONF_ACCOUNT_PHONE = "phone"
CONF_ACCOUNT_ACCESS_TOKEN = "access_token"
CONF_ACCOUNT_REFRESH_TOKEN = "refresh_token"
CONF_ACCOUNT_DEVICE_ID = "device_id"
CONF_ACCOUNT_GWID = "gw_id"
CONF_ACCOUNT_BEAN_ID = "bean_id"
CONF_ACCOUNT_TOKEN_ISSUED_AT = "token_issued_at"
CONF_ACCOUNT_EXPIRES_IN = "expires_in"
CONF_API_REGION = "region"
CONF_POLL_INTERVAL = "poll_interval"

REGIONS = {
    "eu": {
        "h5_gateway": "eu-h5-gateway.gwmcloud.com",
        "app_gateway": "eu-app-gateway.gwmcloud.com",
        "data_upload_gateway": "eu-data-upload-gateway.gwmcloud.com",
        "common_gateway": "eu-app-gateway-common.gwmcloud.com",
    }
}
