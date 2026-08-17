"""API client for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
The xStorage Home inverter has poor energy monitoring accuracy. Power measurements
(consumption, production, grid values, load values) are typically 10%-30% higher than
actual values. This affects all energy flow data returned by the API endpoints:
- /api/device/status (energyFlow section)
- All power-related values in watts

Use external energy monitoring for accurate power measurements.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)

# The device rejects tokens after an hour; refresh slightly before that.
TOKEN_LIFETIME = timedelta(minutes=55)


class EatonError(HomeAssistantError):
    """Base error for the Eaton xStorage Home API."""


class EatonConnectionError(EatonError):
    """The device could not be reached."""


class EatonResponseError(EatonError):
    """The device returned a response that could not be interpreted."""


class EatonCommandError(EatonError):
    """The device rejected a command."""


class EatonAuthError(EatonError):
    """The device rejected the supplied credentials."""

    def __init__(self, err_code: str, message: str) -> None:
        """Initialize with the machine-readable error code from the device."""
        super().__init__(message)
        self.err_code = err_code
        self.message = message


def token_store_key(entry_id: str) -> str:
    """Return the .storage key holding the token for a config entry."""
    return f"{DOMAIN}.{entry_id}_token"


def _require_success(endpoint: str, result: dict[str, Any]) -> dict[str, Any]:
    """Raise when the device reports a command as unsuccessful."""
    if not result.get("successful", result.get("result") is not None):
        raise EatonCommandError(f"Device rejected {endpoint}: {result}")
    return result


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
        user_type: str = "tech",
        verify_ssl: bool = False,
        entry_id: str | None = None,
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
        self.user_type = user_type  # "customer" or "tech"
        self.verify_ssl = verify_ssl
        self.access_token: str | None = None
        self.token_expiration: datetime | None = None
        self._session = async_get_clientsession(hass, verify_ssl=verify_ssl)
        self._auth_lock = asyncio.Lock()
        # Config flow probes have no entry yet and must not persist a token.
        self._store: Store | None = (
            Store(hass, 1, token_store_key(entry_id)) if entry_id else None
        )

    async def connect(self) -> None:
        """Authenticate with the device and get access token."""
        url = f"https://{self.host}/api/auth/signin"

        payload: dict[str, Any] = {
            "username": self.username,
            "pwd": self.password,
            "userType": self.user_type,
        }

        # Only include inverterSn and email for technician accounts
        if self.user_type == "tech":
            payload["inverterSn"] = self.inverter_sn
            payload["email"] = self.email

        try:
            async with self._session.post(
                url, json=payload, timeout=REQUEST_TIMEOUT
            ) as response:
                status = response.status
                is_json = response.content_type == "application/json"
                body: Any = await response.json() if is_json else await response.text()
        except TimeoutError as err:
            raise EatonConnectionError("Authentication timed out") from err
        except aiohttp.ClientError as err:
            raise EatonConnectionError(f"Cannot connect to device: {err}") from err

        if not is_json:
            _LOGGER.error("Non-JSON auth response (%s): %s", status, body)
            # A login page or a proxy error is a reachability problem, not a
            # rejected credential; raising an auth error would prompt reauth.
            raise EatonConnectionError(
                f"Sign-in returned a non-JSON response (status {status})"
            )

        if not isinstance(body, dict):
            raise EatonResponseError(
                f"Sign-in returned an unexpected payload (status {status}): {body}"
            )

        if (
            status == 200
            and body.get("successful")
            and "token" in body.get("result", {})
        ):
            self.access_token = body["result"]["token"]
            self.token_expiration = datetime.now(UTC) + TOKEN_LIFETIME
            await self.store_token()
            _LOGGER.debug("Connected successfully, bearer token acquired")
            return

        error = body.get("error")
        if isinstance(error, dict):
            raise EatonAuthError(
                str(error.get("errCode") or ""),
                str(error.get("description") or "Authentication failed"),
            )

        _LOGGER.warning("Authentication failed: %s", body)
        raise EatonConnectionError(
            "Sign-in returned no token and no error the device explains"
        )

    async def store_token(self) -> None:
        """Store the access token to persistent storage."""
        if self._store is None:
            return
        await self._store.async_save(
            {
                "access_token": self.access_token,
                "token_expiration": self.token_expiration.isoformat()
                if self.token_expiration
                else None,
            }
        )

    async def load_token(self) -> None:
        """Load the access token from persistent storage."""
        if self._store is None:
            return
        data = await self._store.async_load()
        if not data:
            return
        self.access_token = data.get("access_token")
        expiration_str = data.get("token_expiration")
        if expiration_str:
            # Normalize naive datetimes from older versions to timezone-aware
            loaded_dt = datetime.fromisoformat(expiration_str)
            if loaded_dt.tzinfo is None:
                self.token_expiration = loaded_dt.replace(tzinfo=UTC)
            else:
                self.token_expiration = loaded_dt

    async def remove_token(self) -> None:
        """Remove the persisted access token."""
        if self._store is not None:
            await self._store.async_remove()

    async def refresh_token(self) -> None:
        """Refresh the access token."""
        _LOGGER.debug("Refreshing access token")
        await self.connect()

    def _token_valid(self) -> bool:
        """Return True if a usable, unexpired token is held."""
        return bool(
            self.access_token
            and self.token_expiration
            and datetime.now(UTC) < self.token_expiration
        )

    async def ensure_token_valid(self) -> None:
        """Ensure the access token is valid and refresh if needed."""
        if self._token_valid():
            return
        async with self._auth_lock:
            # Another concurrent request may have refreshed while we waited.
            if self._token_valid():
                return
            if self.access_token is None:
                await self.load_token()
                if self._token_valid():
                    return
            await self.refresh_token()

    async def _send(
        self, method: str, url: str, kwargs: dict[str, Any]
    ) -> tuple[int, Any]:
        """Perform a single HTTP request and return its status and body."""
        try:
            async with self._session.request(method, url, **kwargs) as response:
                if response.content_type == "application/json":
                    return response.status, await response.json()
                return response.status, await response.text()
        except TimeoutError as err:
            raise EatonConnectionError(f"Request to {url} timed out") from err
        except aiohttp.ClientError as err:
            raise EatonConnectionError(
                f"Network error requesting {url}: {err}"
            ) from err

    async def make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Raises EatonConnectionError / EatonResponseError instead of returning an
        error payload, so callers can treat "no exception" as success.
        """
        await self.ensure_token_valid()

        url = f"https://{self.host}{endpoint}"
        headers = dict(kwargs.get("headers", {}))
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        if params:
            kwargs["params"] = params

        status, body = await self._send(method, url, kwargs)
        if status == 401:
            _LOGGER.debug("Access token rejected by %s, re-authenticating", endpoint)
            await self.refresh_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            status, body = await self._send(method, url, kwargs)

        # A 401 that survives a fresh token means the account no longer has
        # access, which reauth can resolve; anything else is a hard failure.
        if status == 401:
            raise EatonAuthError("401", f"{endpoint} rejected the access token")
        if status >= 400:
            raise EatonResponseError(f"{endpoint} returned HTTP {status}: {body}")

        if isinstance(body, dict):
            return body

        # Some write endpoints answer with an empty body on success.
        if status < 300 and not str(body).strip():
            return {}

        raise EatonResponseError(
            f"Non-JSON response from {endpoint} (status {status}): {body}"
        )

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
        params: dict[str, Any] = {}
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
        return _require_success(
            "mark all notifications read",
            await self.make_request("POST", "/api/notifications/read/all"),
        )

    async def set_device_power(self, state: bool) -> dict[str, Any]:
        """Control the power state of the device (on/off).

        This endpoint answers 200 with a bare JSON "" rather than a result
        object, so there is nothing to check for success. See
        docs/device-api-behaviour.md.
        """
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
        return _require_success(
            command,
            await self.make_request("POST", "/api/device/command", json=payload),
        )

    async def update_settings(self, settings_data: dict[str, Any]) -> dict[str, Any]:
        """Update device settings via PUT /api/settings.

        The device redirects this to the trailing-slash path with a 307, which
        aiohttp follows while preserving the method.
        """
        _LOGGER.debug(
            "Sending settings update: %s",
            json.dumps(settings_data, separators=(",", ":")),
        )
        return _require_success(
            "settings update",
            await self.make_request("PUT", "/api/settings", json=settings_data),
        )
