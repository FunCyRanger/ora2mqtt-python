"""Mock API responses for testing."""

LOGIN_SUCCESS_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "accessToken": "test_access_token_12345",
        "refreshToken": "test_refresh_token_67890",
        "expiresIn": 7200,
        "userId": "user_123456",
    },
}

ERROR_RATE_LIMIT_308024 = {
    "code": "308024",
    "description": "Rate limit exceeded. A code was sent recently.",
}

ERROR_OTHER_308025 = {
    "code": "308025",
    "description": "Some other error",
}

LOGIN_SMS_SUCCESS_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "accessToken": "sms_access_token_abcde",
        "refreshToken": "sms_refresh_token_fghij",
        "expiresIn": 7200,
        "userId": "user_789012",
    },
}

REFRESH_TOKEN_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "accessToken": "new_access_token_xyz",
        "refreshToken": "new_refresh_token_uvw",
        "expiresIn": 7200,
    },
}

USER_INFO_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "userId": "user_123456",
        "nickName": "Test User",
        "phone": "+491234567890",
    },
}

VEHICLES_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": [
        {
            "vin": "LHG12345678901234",
            "brandName": "ORA",
            "appShowSeriesName": "Funky Cat",
            "vtype": "Funky Cat",
            "deviceId": "device_001",
        },
        {
            "vin": "LHG98765432109876",
            "brandName": "ORA",
            "appShowSeriesName": "Funky Cat",
            "vtype": "Funky Cat",
            "deviceId": "device_002",
        },
    ],
}

VEHICLE_STATUS_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "vin": "LHG12345678901234",
        "acquisitionTime": 1704067200000,
        "updateTime": 1704067200000,
        "deviceId": "device_001",
        "latitude": 52.520008,
        "longitude": 13.404954,
        "items": [
            {"code": "2011501", "value": "250", "unit": "km"},
            {"code": "2013021", "value": "75", "unit": "%"},
            {"code": "2013022", "value": "30", "unit": "min"},
            {"code": "2013023", "value": "80", "unit": "%"},
            {"code": "2041142", "value": "1"},
            {"code": "2041301", "value": "72", "unit": "%"},
            {"code": "2042082", "value": "1"},
            {"code": "2078020", "value": "0"},
            {"code": "2101001", "value": "230", "unit": "kPa"},
            {"code": "2101002", "value": "230", "unit": "kPa"},
            {"code": "2101003", "value": "235", "unit": "kPa"},
            {"code": "2101004", "value": "235", "unit": "kPa"},
            {"code": "2101005", "value": "22", "unit": "°C"},
            {"code": "2101006", "value": "23", "unit": "°C"},
            {"code": "2101007", "value": "21", "unit": "°C"},
            {"code": "2101008", "value": "22", "unit": "°C"},
            {"code": "2103010", "value": "15430", "unit": "km"},
            {"code": "2201001", "value": "215", "unit": "°C"},
            {"code": "2202001", "value": "1"},
            {"code": "2208001", "value": "1"},
            {"code": "2210001", "value": "1"},
            {"code": "2210002", "value": "1"},
            {"code": "2210003", "value": "1"},
            {"code": "2210004", "value": "1"},
            {"code": "2222001", "value": "0"},
        ],
    },
}

ERROR_RESPONSE = {
    "code": "100001",
    "description": "Invalid parameter",
}

TOKEN_EXPIRED_RESPONSE = {
    "code": "110002",
    "description": "Access token expired",
}


def get_fake_vehicle_status(vin: str = "LHG12345678901234") -> dict:
    """Generate a vehicle status response with custom VIN."""
    data = dict(VEHICLE_STATUS_RESPONSE)
    data["data"]["vin"] = vin
    return data


def get_expected_sensors() -> list[dict]:
    """Return expected sensor configurations."""
    return [
        {"code": 2013021, "name": "SOC", "unit": "%", "device_class": "battery"},
        {"code": 2011501, "name": "Range", "unit": "km", "device_class": "distance"},
        {"code": 2103010, "name": "Odometer", "unit": "km", "device_class": "distance"},
        {"code": 2041301, "name": "SOCE", "unit": "%", "device_class": None},
        {
            "code": 2201001,
            "name": "Interior Temperature",
            "unit": "°C",
            "device_class": "temperature",
        },
        {"code": 2101001, "name": "Tire Pressure FL", "unit": "kPa", "device_class": "pressure"},
        {"code": 2101002, "name": "Tire Pressure FR", "unit": "kPa", "device_class": "pressure"},
        {"code": 2101003, "name": "Tire Pressure RL", "unit": "kPa", "device_class": "pressure"},
        {"code": 2101004, "name": "Tire Pressure RR", "unit": "kPa", "device_class": "pressure"},
        {
            "code": 2101005,
            "name": "Tire Temperature FL",
            "unit": "°C",
            "device_class": "temperature",
        },
        {
            "code": 2101006,
            "name": "Tire Temperature FR",
            "unit": "°C",
            "device_class": "temperature",
        },
        {
            "code": 2101007,
            "name": "Tire Temperature RL",
            "unit": "°C",
            "device_class": "temperature",
        },
        {
            "code": 2101008,
            "name": "Tire Temperature RR",
            "unit": "°C",
            "device_class": "temperature",
        },
    ]


def get_expected_binary_sensors() -> list[dict]:
    """Return expected binary sensor configurations."""
    return [
        {"code": 2202001, "name": "A/C", "device_class": "running"},
        {"code": 2208001, "name": "Lock", "device_class": "lock"},
        {"code": 2042082, "name": "Charge Plug", "device_class": "plug"},
        {"code": 2041142, "name": "Charging Active", "device_class": "heat"},
        {"code": 2078020, "name": "Air Circulation", "device_class": "running"},
        {"code": 2222001, "name": "Front Defroster", "device_class": "heat"},
        {"code": 2210001, "name": "Window FL", "device_class": "window"},
        {"code": 2210002, "name": "Window FR", "device_class": "window"},
        {"code": 2210003, "name": "Window RL", "device_class": "window"},
        {"code": 2210004, "name": "Window RR", "device_class": "window"},
    ]


REMOTE_CTRL_SUCCESS_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "seqNo": "SEQ12345",
    },
}

T5_SEND_CMD_SUCCESS_RESPONSE = {
    "code": "000000",
    "description": "Success",
    "data": {
        "seqNo": "T5SEQ67890",
    },
}

GET_REMOTE_CTRL_RESULT_SUCCESS = {
    "code": "000000",
    "description": "Success",
    "data": [
        {
            "seqNo": "T5SEQ67890",
            "result": "success",
            "resultCode": "0",
            "message": "Command executed successfully",
        }
    ],
}

GET_REMOTE_CTRL_RESULT_MULTIPLE = {
    "code": "000000",
    "description": "Success",
    "data": [
        {"seqNo": "T5SEQ001", "result": "success", "resultCode": "0", "message": "OK"},
        {"seqNo": "T5SEQ002", "result": "failed", "resultCode": "1", "message": "Timeout"},
    ],
}
