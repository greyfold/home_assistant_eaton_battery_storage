"""API client for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
The xStorage Home inverter has poor energy monitoring accuracy. Power measurements
(consumption, production, grid values, load values) are typically 30% higher than
actual values. This affects all energy flow data returned by the API endpoints:
- /api/device/status (energyFlow section)
- /api/metrics and /api/metrics/daily
- All power-related values in watts

Use external energy monitoring for accurate power measurements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


class EatonBatteryAPI:
    """API client for Eaton xStorage Home battery system."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        inverter_sn: str,
        email: str,
        app_id: str,
        name: str,
        manufacturer: str,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.inverter_sn = inverter_sn
        self.email = email
        self.app_id = app_id
        self.name = name
        self.manufacturer = manufacturer
        self.access_token: str | None = None
        self.token_expiration: datetime | None = None
        self.store = Store(hass, 1, f"{host}_token")

    async def connect(self) -> None:
        """Authenticate with the device and get access token."""
        url = f"https://{self.host}/api/auth/signin"
        payload = {
            "username": self.username,
            "pwd": self.password,
            "inverterSn": self.inverter_sn,
            "email": self.email,
            "userType": "tech",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, ssl=False) as response:
                    if response.content_type == "application/json":
                        result = await response.json()
                    else:
                        text = await response.text()
                        _LOGGER.error(
                            "Non-JSON auth response (%s): %s", response.status, text
                        )
                        raise ValueError("Authentication failed: non-JSON response")

                    if (
                        response.status == 200
                        and result.get("successful")
                        and "token" in result.get("result", {})
                    ):
                        self.access_token = result["result"]["token"]
                        self.token_expiration = datetime.utcnow() + timedelta(
                            minutes=55
                        )
                        await self.store_token()
                        _LOGGER.info("Connected successfully. Bearer token acquired.")
                    elif "error" in result:
                        err = result["error"]
                        err_msg = (
                            err.get("description")
                            or err.get("errCode")
                            or "Authentication failed"
                        )
                        raise ValueError(err_msg)
                    else:
                        _LOGGER.warning("Authentication failed: %s", result)
                        raise ValueError(
                            "Authentication failed with unexpected response."
                        )
            except aiohttp.ClientError as e:
                _LOGGER.error("Network error during authentication: %s", e)
                raise ConnectionError(f"Cannot connect to device: {e}") from e
            except Exception as e:
                _LOGGER.error("Error during authentication: %s", e)
                raise

    async def store_token(self) -> None:
        """Store the access token to persistent storage."""
        await self.store.async_save(
            {
                "access_token": self.access_token,
                "token_expiration": self.token_expiration.isoformat()
                if self.token_expiration
                else None,
            }
        )

    async def load_token(self) -> None:
        """Load the access token from persistent storage."""
        data = await self.store.async_load()
        if data:
            self.access_token = data.get("access_token")
            expiration_str = data.get("token_expiration")
            if expiration_str:
                self.token_expiration = datetime.fromisoformat(expiration_str)

    async def refresh_token(self) -> None:
        """Refresh the access token."""
        _LOGGER.info("Refreshing access token...")
        await self.connect()

    async def ensure_token_valid(self) -> None:
        """Ensure the access token is valid and refresh if needed."""
        if (
            not self.access_token
            or not self.token_expiration
            or datetime.utcnow() >= self.token_expiration
        ):
            _LOGGER.info("Token missing or expired. Re-authenticating...")
            await self.refresh_token()

    async def make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated API request."""
        await self.ensure_token_valid()

        url = f"https://{self.host}{endpoint}"
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers
        kwargs["ssl"] = False

        # Add query parameters if provided
        if params:
            kwargs["params"] = params

        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 401:
                        _LOGGER.warning("Access token expired. Refreshing token...")
                        await self.refresh_token()
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        kwargs["headers"] = headers
                        async with session.request(
                            method, url, **kwargs
                        ) as retry_response:
                            if retry_response.content_type == "application/json":
                                return await retry_response.json()
                            text_response = await retry_response.text()
                            _LOGGER.error(
                                "Non-JSON response from %s: Status %s, Content: %s",
                                endpoint,
                                retry_response.status,
                                text_response,
                            )
                            return {"successful": False, "error": text_response}

                    # Handle different response types
                    if response.content_type == "application/json":
                        return await response.json()
                    text_response = await response.text()
                    _LOGGER.error(
                        "Non-JSON response from %s: Status %s, Content: %s",
                        endpoint,
                        response.status,
                        text_response,
                    )
                    return {
                        "successful": False,
                        "error": text_response,
                        "status": response.status,
                    }

            except aiohttp.ClientError as e:
                _LOGGER.error("Network error during API request to %s: %s", endpoint, e)
                return {"successful": False, "error": str(e)}
            except Exception as e:
                _LOGGER.error("Error during API request to %s: %s", endpoint, e)
                return {"successful": False, "error": str(e)}

    async def get_status(self) -> dict[str, Any]:
        """Get device status."""
        return await self.make_request("GET", "/api/device/status")

    async def get_device(self) -> dict[str, Any]:
        """Get device information."""
        return await self.make_request("GET", "/api/device")

    async def get_config_state(self) -> dict[str, Any]:
        """Get configuration state."""
        return await self.make_request("GET", "/api/config/state")

    async def get_settings(self) -> dict[str, Any]:
        """Get device settings."""
        return await self.make_request("GET", "/api/settings")

    async def get_metrics(self) -> dict[str, Any]:
        """Get device metrics."""
        return await self.make_request("GET", "/api/metrics")

    async def get_metrics_daily(self) -> dict[str, Any]:
        """Get daily metrics."""
        return await self.make_request("GET", "/api/metrics/daily")

    async def get_schedule(self) -> dict[str, Any]:
        """Get device schedule."""
        return await self.make_request("GET", "/api/schedule/")

    async def get_technical_status(self) -> dict[str, Any]:
        """Get technical status."""
        return await self.make_request("GET", "/api/technical/status")

    async def get_maintenance_diagnostics(self) -> dict[str, Any]:
        """Get maintenance diagnostics."""
        return await self.make_request("GET", "/api/device/maintenance/diagnostics")

    async def get_notifications(
        self,
        status: str | None = None,
        size: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Get notifications with optional filtering."""
        params = {}
        if status:
            params["status"] = status
        if size is not None:
            params["size"] = size
        if offset is not None:
            params["offset"] = offset

        return await self.make_request("GET", "/api/notifications/", params=params)

    async def get_unread_notifications_count(self) -> dict[str, Any]:
        """Get count of unread notifications."""
        return await self.make_request("GET", "/api/notifications/unread")

    async def mark_all_notifications_read(self) -> dict[str, Any]:
        """Mark all notifications as read."""
        return await self.make_request("POST", "/api/notifications/read/all")

    async def set_device_power(self, state: bool) -> dict[str, Any]:
        """Control the power state of the device (on/off)."""
        payload = {"parameters": {"state": state}}
        return await self.make_request("POST", "/api/device/power", json=payload)

    async def send_device_command(
        self, command: str, duration: int, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to the device via POST /api/device/command."""
        payload = {
            "command": command,
            "duration": duration,
            "parameters": parameters or {},
        }
        _LOGGER.debug(
            "Sending device command: %s", json.dumps(payload, separators=(",", ":"))
        )
        return await self.make_request("POST", "/api/device/command", json=payload)

    async def update_settings(self, settings_data: dict[str, Any]) -> dict[str, Any]:
        """Update device settings via PUT /api/settings."""
        _LOGGER.debug(
            "Sending settings update: %s",
            json.dumps(settings_data, separators=(",", ":")),
        )
        return await self.make_request("PUT", "/api/settings", json=settings_data)
