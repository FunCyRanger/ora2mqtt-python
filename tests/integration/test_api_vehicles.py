"""Integration tests for vehicle client."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ora.api.vehicles import (
    GwmVehicleClient,
    Vehicle,
    VehicleStatus,
)
from tests.fixtures.api_responses import (
    GET_REMOTE_CTRL_RESULT_MULTIPLE,
    GET_REMOTE_CTRL_RESULT_SUCCESS,
    REMOTE_CTRL_SUCCESS_RESPONSE,
    T5_SEND_CMD_SUCCESS_RESPONSE,
    VEHICLE_STATUS_RESPONSE,
    VEHICLES_RESPONSE,
)


class TestGwmVehicleClient:
    """Test GwmVehicleClient."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.get = AsyncMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def vehicle_client(self, mock_client):
        return GwmVehicleClient(mock_client)

    @pytest.mark.asyncio
    async def test_acquire_vehicles(self, vehicle_client, mock_client):
        """Test acquiring vehicles."""
        mock_client.get.return_value = VEHICLES_RESPONSE

        result = await vehicle_client.acquire_vehicles()

        assert len(result) == 2
        assert all(isinstance(v, Vehicle) for v in result)
        assert result[0].vin == "LHG12345678901234"
        assert result[0].brand_name == "ORA"
        assert result[0].app_show_series_name == "Funky Cat"
        assert result[1].vin == "LHG98765432109876"

        mock_client.get.assert_called_once_with(
            "globalapp/vehicle/acquireVehicles", use_app_gateway=True
        )

    @pytest.mark.asyncio
    async def test_acquire_vehicles_empty(self, vehicle_client, mock_client):
        """Test acquiring vehicles when none exist."""
        mock_client.get.return_value = {"code": "000000", "data": []}

        result = await vehicle_client.acquire_vehicles()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_vehicle_basics(self, vehicle_client, mock_client):
        """Test getting vehicle basics."""
        mock_client.get.return_value = {
            "code": "000000",
            "data": {"vin": "LHG12345678901234", "model": "Funky Cat"},
        }

        result = await vehicle_client.get_vehicle_basics("LHG12345678901234")

        mock_client.get.assert_called_once_with(
            "vehicle/vehicleBasicsInfo?vin=LHG12345678901234&flag=true",
            use_app_gateway=True,
        )
        assert result["data"]["vin"] == "LHG12345678901234"

    @pytest.mark.asyncio
    async def test_get_last_status(self, vehicle_client, mock_client):
        """Test getting last vehicle status."""
        mock_client.get.return_value = VEHICLE_STATUS_RESPONSE

        result = await vehicle_client.get_last_status("LHG12345678901234")

        assert isinstance(result, VehicleStatus)
        assert result.vin == "LHG12345678901234"
        assert result.acquisition_time == 1704067200000
        assert result.latitude == 52.520008
        assert result.longitude == 13.404954
        assert len(result.items) == 25

        # Verify some specific items
        soc_item = next(i for i in result.items if i.code == 2013021)
        assert soc_item.value == "75"
        assert soc_item.unit == "%"

        range_item = next(i for i in result.items if i.code == 2011501)
        assert range_item.value == "250"

        lock_item = next(i for i in result.items if i.code == 2208001)
        assert lock_item.value == "1"

    @pytest.mark.asyncio
    async def test_remote_control(self, vehicle_client, mock_client):
        """Test sending remote control command."""
        mock_client.post.return_value = {"code": "000000", "data": {}}

        await vehicle_client.remote_control(
            vin="LHG12345678901234",
            command="lock",
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        args, kwargs = call_args
        assert args[1]["vin"] == "LHG12345678901234"
        assert args[1]["command"] == "lock"

    @pytest.mark.asyncio
    async def test_remote_control_with_params(self, vehicle_client, mock_client):
        """Test sending remote control command with parameters."""
        mock_client.post.return_value = {"code": "000000", "data": {}}

        await vehicle_client.remote_control(
            vin="LHG12345678901234",
            command="climate",
            params={"temperature": 22, "ac": "on"},
        )

        call_args = mock_client.post.call_args
        args, kwargs = call_args
        data = args[1]
        assert data["temperature"] == 22
        assert data["ac"] == "on"

    @pytest.mark.asyncio
    async def test_send_t5_command(self, vehicle_client, mock_client):
        """Test sending T5 command."""
        mock_client.post.return_value = {"code": "000000", "data": {}}

        await vehicle_client.send_t5_command(
            vin="LHG12345678901234",
            command="unlock",
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        args, kwargs = call_args
        assert args[0] == "vehicle/T5/sendCmd"
        assert kwargs["use_app_gateway"] is True

    @pytest.mark.asyncio
    async def test_remote_control_logs_send_and_result(self, vehicle_client, mock_client, caplog):
        """Test remote_control logs SEND_TELEGRAM messages."""
        mock_client.post.return_value = REMOTE_CTRL_SUCCESS_RESPONSE

        with caplog.at_level(logging.INFO):
            await vehicle_client.remote_control(
                vin="LHG12345678901234",
                command="lock",
                params={"foo": "bar"},
            )

        assert any("SEND_TELEGRAM remote_control:" in r.message for r in caplog.records)
        assert any("vin=L..15..4" in r.message for r in caplog.records)
        assert any("command=lock" in r.message for r in caplog.records)
        assert any("SEND_TELEGRAM remote_control result:" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_send_t5_command_logs_send_and_result(self, vehicle_client, mock_client, caplog):
        """Test send_t5_command logs SEND_TELEGRAM messages."""
        mock_client.post.return_value = T5_SEND_CMD_SUCCESS_RESPONSE

        with caplog.at_level(logging.INFO):
            await vehicle_client.send_t5_command(
                vin="LHG12345678901234",
                command="unlock",
                params={"timeout": 60},
            )

        assert any("SEND_TELEGRAM send_t5_command:" in r.message for r in caplog.records)
        assert any("vin=L..15..4" in r.message for r in caplog.records)
        assert any("command=unlock" in r.message for r in caplog.records)
        assert any("SEND_TELEGRAM send_t5_command result:" in r.message for r in caplog.records)


class TestGetRemoteCtrlResult:
    """Test get_remote_ctrl_result."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.get = AsyncMock()
        return client

    @pytest.fixture
    def vehicle_client(self, mock_client):
        return GwmVehicleClient(mock_client)

    @pytest.mark.asyncio
    async def test_get_remote_ctrl_result_logs_send_and_parsed(
        self, vehicle_client, mock_client, caplog
    ):
        """Test get_remote_ctrl_result logs SEND_TELEGRAM messages."""
        mock_client.get.return_value = GET_REMOTE_CTRL_RESULT_SUCCESS

        with caplog.at_level(logging.INFO):
            results = await vehicle_client.get_remote_ctrl_result("T5SEQ67890")

        assert any(
            "SEND_TELEGRAM get_remote_ctrl_result: seq_no=TXXXXXXXX0" in r.message
            for r in caplog.records
        )
        assert any("SEND_TELEGRAM get_remote_ctrl_result raw:" in r.message for r in caplog.records)
        assert any(
            "SEND_TELEGRAM get_remote_ctrl_result parsed:" in r.message for r in caplog.records
        )
        assert any("seq_no=TXXXXXXXX0" in r.message for r in caplog.records)
        assert any("result=success" in r.message for r in caplog.records)
        assert any("result_code=0" in r.message for r in caplog.records)
        assert len(results) == 1
        assert results[0].result == "success"
        assert results[0].message == "Command executed successfully"

    @pytest.mark.asyncio
    async def test_get_remote_ctrl_result_multiple_results(
        self, vehicle_client, mock_client, caplog
    ):
        """Test get_remote_ctrl_result with multiple results."""
        mock_client.get.return_value = GET_REMOTE_CTRL_RESULT_MULTIPLE

        with caplog.at_level(logging.INFO):
            results = await vehicle_client.get_remote_ctrl_result("T5SEQ001")

        assert len(results) == 2
        assert results[0].seq_no == "T5SEQ001"
        assert results[0].result == "success"
        assert results[1].seq_no == "T5SEQ002"
        assert results[1].result == "failed"

    @pytest.mark.asyncio
    async def test_get_remote_ctrl_result_empty_data(self, vehicle_client, mock_client, caplog):
        """Test get_remote_ctrl_result when data is empty."""
        mock_client.get.return_value = {"code": "000000", "data": []}

        with caplog.at_level(logging.INFO):
            results = await vehicle_client.get_remote_ctrl_result("SEQ123")

        assert len(results) == 0
        assert any(
            "SEND_TELEGRAM get_remote_ctrl_result parsed:" in r.message for r in caplog.records
        )


class TestVehicleStatusParsing:
    """Test parsing of vehicle status data."""

    @pytest.mark.asyncio
    async def test_status_items_parsing(self):
        """Test that status items are correctly parsed."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=VEHICLE_STATUS_RESPONSE)
        client = GwmVehicleClient(mock_client)

        status = await client.get_last_status("LHG12345678901234")

        # Check tire pressure sensors
        for code in [2101001, 2101002, 2101003, 2101004]:
            item = next((i for i in status.items if i.code == code), None)
            assert item is not None
            assert item.unit == "kPa"

        # Check window sensors
        for code in [2210001, 2210002, 2210003, 2210004]:
            item = next((i for i in status.items if i.code == code), None)
            assert item is not None

        # Check binary sensors
        binary_codes = [2202001, 2208001, 2042082, 2078020, 2222001]
        for code in binary_codes:
            item = next((i for i in status.items if i.code == code), None)
            assert item is not None
            assert item.value in ["0", "1"]
