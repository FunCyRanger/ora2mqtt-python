"""Vehicle API methods for GWM."""

import logging
from dataclasses import dataclass
from typing import Any

from ..privacy import mask_privacy_string, sanitize_for_logging
from .client import GwmHttpClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class Vehicle:
    """Vehicle information."""

    vin: str
    brand_name: str
    app_show_series_name: str
    vtype: str
    device_id: str | None = None


@dataclass
class VehicleStatusItem:
    """Single status item from vehicle."""

    code: int
    value: Any
    unit: str | None = None


@dataclass
class VehicleStatus:
    """Vehicle status data."""

    vin: str
    acquisition_time: int
    update_time: int
    device_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    items: list[VehicleStatusItem] | None = None


@dataclass
class Country:
    """Country information."""

    code: str
    name: str
    lang_code: str


@dataclass
class RemoteCtrlResult:
    """Remote control result."""

    seq_no: str
    result: str
    result_code: str
    message: str


class GwmVehicleClient:
    """Vehicle API client for GWM."""

    def __init__(self, client: GwmHttpClient):
        self._client = client

    async def acquire_vehicles(self) -> list[Vehicle]:
        """Get list of vehicles for the user."""
        _LOGGER.info("ORA: acquire_vehicles")
        result = await self._client.get("globalapp/vehicle/acquireVehicles", use_app_gateway=True)

        data = result.get("data", [])
        vehicles = []
        for v in data:
            vehicles.append(
                Vehicle(
                    vin=v.get("vin", ""),
                    brand_name=v.get("brandName", ""),
                    app_show_series_name=v.get("appShowSeriesName", ""),
                    vtype=v.get("vtype", ""),
                    device_id=v.get("deviceId"),
                )
            )
        _LOGGER.info("ORA: acquire_vehicles found %d vehicle(s)", len(vehicles))
        return vehicles

    async def get_vehicle_basics(self, vin: str) -> dict:
        """Get vehicle basic information."""
        return await self._client.get(
            f"vehicle/vehicleBasicsInfo?vin={vin}&flag=true",
            use_app_gateway=True,
        )

    async def get_last_status(self, vin: str) -> VehicleStatus:
        """Get the last known status of a vehicle."""
        _LOGGER.info("ORA: get_last_status vin=%s", mask_privacy_string(vin))
        result = await self._client.get(
            f"vehicle/getLastStatus?vin={vin}&seqNo=",
            use_app_gateway=True,
        )

        data = result.get("data", {})

        items = []
        for item in data.get("items", []):
            code = int(item.get("code", 0))
            value = item.get("value")
            unit = item.get("unit")
            items.append(VehicleStatusItem(code=code, value=value, unit=unit))

        _LOGGER.info("ORA: get_last_status complete vin=%s items=%d", mask_privacy_string(vin), len(items))
        return VehicleStatus(
            vin=vin,
            acquisition_time=int(data.get("acquisitionTime", 0)),
            update_time=int(data.get("updateTime", 0)),
            device_id=data.get("deviceId"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            items=items,
        )

    async def get_countries(self) -> list[Country]:
        """Get list of available countries."""
        result = await self._client.get(
            "country/getCountrys",
            use_app_gateway=False,
        )

        countries = []
        data = result.get("data", {})

        for letter, country_list in data.items():
            if country_list:
                for c in country_list:
                    countries.append(
                        Country(
                            code=c.get("countryCode", ""),
                            name=c.get("countryName", ""),
                            lang_code=c.get("langCode", ""),
                        )
                    )

        return countries

    async def remote_control(
        self,
        vin: str,
        command: str,
        params: dict | None = None,
    ) -> dict:
        """Send remote control command to vehicle."""
        data = {
            "vin": vin,
            "command": command,
            **(params or {}),
        }
        _LOGGER.info(
            "SEND_TELEGRAM remote_control: vin=%s command=%s params=%s",
            mask_privacy_string(vin),
            command,
            sanitize_for_logging(params),
        )
        result = await self._client.post(
            "vehicle/modifyVehicleRemoteCtlInfo",
            data,
        )
        _LOGGER.info("SEND_TELEGRAM remote_control result: %s", sanitize_for_logging(result))
        return result

    async def send_t5_command(
        self,
        vin: str,
        command: str,
        params: dict | None = None,
    ) -> dict:
        """Send T5 command to vehicle (more commands)."""
        data = {
            "vin": vin,
            "command": command,
            **(params or {}),
        }
        _LOGGER.info(
            "SEND_TELEGRAM send_t5_command: vin=%s command=%s params=%s",
            mask_privacy_string(vin),
            command,
            sanitize_for_logging(params),
        )
        result = await self._client.post(
            "vehicle/T5/sendCmd",
            data,
            use_app_gateway=True,
        )
        _LOGGER.info("SEND_TELEGRAM send_t5_command result: %s", sanitize_for_logging(result))
        return result

    async def get_remote_ctrl_result(self, seq_no: str) -> list[RemoteCtrlResult]:
        """Get remote control result by sequence number.

        Args:
            seq_no: The sequence number returned from send_t5_command

        Returns:
            List of remote control results
        """
        _LOGGER.info("SEND_TELEGRAM get_remote_ctrl_result: seq_no=%s", mask_privacy_string(seq_no))
        result = await self._client.get(
            f"vehicle/getRemoteCtrlResultT5?seqNo={seq_no}",
            use_app_gateway=True,
        )
        _LOGGER.info("SEND_TELEGRAM get_remote_ctrl_result raw: %s", sanitize_for_logging(result))

        data = result.get("data", [])
        results = []

        for item in data:
            results.append(
                RemoteCtrlResult(
                    seq_no=item.get("seqNo", ""),
                    result=item.get("result", ""),
                    result_code=item.get("resultCode", ""),
                    message=item.get("message", ""),
                )
            )

        _LOGGER.info(
            "SEND_TELEGRAM get_remote_ctrl_result parsed: seq_no=%s result=%s result_code=%s message=%s",
            results[0].seq_no if results else "",
            results[0].result if results else "",
            results[0].result_code if results else "",
            results[0].message if results else "",
        )
        return results
