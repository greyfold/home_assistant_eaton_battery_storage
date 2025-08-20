import aiohttp
import logging
from datetime import datetime, timedelta
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

class EatonBatteryAPI:
    def __init__(
        self,
        hass,
        host,
        username,
        password,
        app_id,
        name,
        manufacturer,
        inverter_sn: str | None = None,
        email: str | None = None,
        user_type: str = "customer",
    ):
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.app_id = app_id
        self.name = name
        self.manufacturer = manufacturer
        # Optional fields for technician login
        self.inverter_sn = inverter_sn
        self.email = email
        self.user_type = user_type
        self.access_token = None
        self.token_expiration = None
        self.store = Store(hass, 1, f"{host}_token")

    async def connect(self):
        url = f"https://{self.host}/api/auth/signin"
        payload = {
            "username": self.username,
            "pwd": self.password,
            "userType": self.user_type or "customer",
        }
        # Provide optional fields only when available
        if self.inverter_sn:
            payload["inverterSn"] = self.inverter_sn
        if self.email:
            payload["email"] = self.email

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, ssl=False) as response:
                    # Prefer JSON response when available
                    if response.content_type == "application/json":
                        result = await response.json()
                    else:
                        text = await response.text()
                        _LOGGER.error("Non-JSON auth response (%s): %s", response.status, text)
                        raise ValueError("Authentication failed: non-JSON response")

                    if response.status == 200 and result.get("successful") and "token" in result.get("result", {}):
                        self.access_token = result["result"]["token"]
                        self.token_expiration = datetime.utcnow() + timedelta(minutes=55)
                        await self.store_token()
                        _LOGGER.info("Connected successfully. Bearer token acquired.")
                    elif "error" in result:
                        err = result["error"]
                        err_msg = err.get("description") or err.get("errCode") or "Authentication failed"
                        raise ValueError(err_msg)
                    else:
                        _LOGGER.warning("Authentication failed: %s", result)
                        raise ValueError("Authentication failed with unexpected response.")
            except Exception as e:
                _LOGGER.error("Error during authentication: %s", e)
                raise

    async def store_token(self):
        await self.store.async_save({
            "access_token": self.access_token,
            "token_expiration": self.token_expiration.isoformat() if self.token_expiration else None
        })

    async def load_token(self):
        data = await self.store.async_load()
        if data:
            self.access_token = data.get("access_token")
            expiration_str = data.get("token_expiration")
            if expiration_str:
                self.token_expiration = datetime.fromisoformat(expiration_str)

    async def refresh_token(self):
        _LOGGER.info("Refreshing access token...")
        await self.connect()

    async def ensure_token_valid(self):
        if not self.access_token or not self.token_expiration or datetime.utcnow() >= self.token_expiration:
            _LOGGER.info("Token missing or expired. Re-authenticating...")
            await self.refresh_token()

    async def make_request(self, method, endpoint, params=None, **kwargs):
        await self.ensure_token_valid()

        url = f"https://{self.host}{endpoint}"
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers
        kwargs["ssl"] = False
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
                        async with session.request(method, url, **kwargs) as retry_response:
                            if retry_response.content_type == "application/json":
                                return await retry_response.json()
                            text_resp = await retry_response.text()
                            _LOGGER.error("Non-JSON response from %s (retry): %s", endpoint, text_resp)
                            return {"successful": False, "error": text_resp}

                    if response.content_type == "application/json":
                        return await response.json()
                    text_resp = await response.text()
                    _LOGGER.error("Non-JSON response from %s: status %s content %s", endpoint, response.status, text_resp)
                    return {"successful": False, "error": text_resp, "status": response.status}
            except Exception as e:
                _LOGGER.error("Error during API request to %s: %s", endpoint, e)
                return {}

    async def get_status(self):
        return await self.make_request("GET", "/api/device/status")

    # Additional endpoints (not all may be available for customer accounts)
    async def get_device(self):
        return await self.make_request("GET", "/api/device")

    async def get_config_state(self):
        return await self.make_request("GET", "/api/config/state")

    async def get_settings(self):
        return await self.make_request("GET", "/api/settings")

    async def get_metrics(self):
        return await self.make_request("GET", "/api/metrics")

    async def get_metrics_daily(self):
        return await self.make_request("GET", "/api/metrics/daily")

    async def get_schedule(self):
        return await self.make_request("GET", "/api/schedule/")

    async def get_technical_status(self):
        return await self.make_request("GET", "/api/technical/status")

    async def get_maintenance_diagnostics(self):
        return await self.make_request("GET", "/api/device/maintenance/diagnostics")

    async def get_notifications(self, status=None, size=None, offset=None):
        """Get notifications with optional filtering (defaults to NORMAL)."""
        params = {}
        if status:
            params["status"] = status
        if size is not None:
            params["size"] = size
        if offset is not None:
            params["offset"] = offset
        # Default to device notifications if no filters provided
        endpoint = "/api/notifications/" if params else "/api/device/notifications"
        return await self.make_request("GET", endpoint, params=params or None)

    async def get_unread_notifications_count(self):
        return await self.make_request("GET", "/api/notifications/unread")

    async def mark_all_notifications_read(self):
        return await self.make_request("POST", "/api/notifications/read/all")

    async def set_device_power(self, state: bool):
        payload = {"parameters": {"state": state}}
        return await self.make_request("POST", "/api/device/power", json=payload)

    async def send_device_command(self, command: str, duration: int, parameters: dict | None = None):
        payload = {"command": command, "duration": duration, "parameters": parameters or {}}
        return await self.make_request("POST", "/api/device/command", json=payload)

    async def update_settings(self, settings_data: dict):
        return await self.make_request("PUT", "/api/settings", json=settings_data)
