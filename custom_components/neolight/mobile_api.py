"""Tuya Mobile SDK request signing recovered from the supplied NeoLight APK.

The signature is verified against a request captured from the owner's app.
This module does not store credentials or send network requests.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Awaitable, Callable, Mapping
from uuid import uuid4

from aiohttp import ClientSession, ClientTimeout
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


SIGNED_FIELDS = frozenset({
    "a", "v", "lat", "lon", "lang", "deviceId", "appVersion", "ttid",
    "isH5", "h5Token", "os", "clientId", "postData", "time", "requestId",
    "et", "n4h5", "sid", "chKey", "sp",
})


def _post_data_digest(value: str) -> str:
    """Match ThingApiSignManager.postDataMD5Hex/swapSignString."""
    digest = hashlib.md5(value.encode()).hexdigest()
    return digest[8:16] + digest[:8] + digest[24:32] + digest[16:24]


def sign_mobile_request(parameters: Mapping[str, str], signing_key: str) -> str:
    """Sign the visible form fields exactly as the Android SDK does."""
    parts = []
    for key in sorted(parameters):
        value = parameters[key]
        if key not in SIGNED_FIELDS or not value:
            continue
        if key == "postData":
            value = _post_data_digest(value)
        parts.append(f"{key}={value}")
    message = "||".join(parts).encode()
    return hmac.new(signing_key.encode(), message, hashlib.sha256).hexdigest()


class MobileApiError(Exception):
    """The vendor API rejected a request or returned malformed data."""


class MobileApiClient:
    """Small autonomous client for the observed Tuya Mobile API endpoint."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        static_fields: Mapping[str, str],
        signing_key: str,
        sid: str = "",
        email: str = "",
        password: str = "",
        country_code: str = "380",
        on_login: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._static_fields = dict(static_fields)
        self._signing_key = signing_key
        self.sid = sid
        self._email = email
        self._password = password
        self._country_code = country_code
        self._on_login = on_login

    async def request(
        self, action: str, version: str, post_data: Mapping[str, Any] | None = None
    ) -> Any:
        fields = dict(self._static_fields)
        fields.update({
            "a": action,
            "v": version,
            "et": "0.0.1",
            "time": str(int(time.time())),
            "requestId": str(uuid4()),
            "sid": self.sid,
        })
        if post_data is not None:
            fields["postData"] = json.dumps(post_data, separators=(",", ":"), ensure_ascii=False)
        fields["sign"] = sign_mobile_request(fields, self._signing_key)
        async with self._session.post(
            f"https://{self._host}/api.json",
            data=fields,
            timeout=ClientTimeout(total=15),
        ) as response:
            response.raise_for_status()
            body = await response.json()
        if body.get("success") is not True:
            raise MobileApiError(body.get("errorCode") or body.get("status") or "API rejected request")
        return body.get("result")

    async def read_device(self, device_id: str) -> dict[str, Any]:
        try:
            result = await self.request("tuya.m.device.get", "1.0", {"devId": device_id})
        except MobileApiError as error:
            if str(error) not in {"USER_SESSION_INVALID", "USER_SESSION_LOSS", "USER_SESSION_EXPIRED"}:
                raise
            await self.login()
            result = await self.request("tuya.m.device.get", "1.0", {"devId": device_id})
        if not isinstance(result, dict) or result.get("devId") != device_id:
            raise MobileApiError("Unexpected device response")
        return result

    async def publish_dps(self, device_id: str, command: Mapping[str, Any]) -> None:
        """Send an already validated DP command through the app's cloud API."""
        result = await self.request(
            "thing.m.device.dp.publish", "1.0",
            {
                "gwId": device_id,
                "devId": device_id,
                "dps": json.dumps(command, separators=(",", ":")),
            },
        )
        if result is not True:
            raise MobileApiError("DP publish was not acknowledged")

    async def login(self) -> dict[str, Any]:
        """Perform the APK's token + RSA email/password login flow once."""
        if not self._email or not self._password:
            raise MobileApiError("Account credentials are not configured")
        old_sid = self.sid
        self.sid = ""
        try:
            token = await self.request(
                "thing.m.user.username.token.get", "2.0",
                {"countryCode": self._country_code, "username": self._email, "isUid": False},
            )
            if not isinstance(token, dict) or not token.get("pbKey") or not token.get("token"):
                raise MobileApiError("Login token lacks an RSA key")
            pem = "-----BEGIN PUBLIC KEY-----\n" + token["pbKey"] + "\n-----END PUBLIC KEY-----"
            public_key = serialization.load_pem_public_key(pem.encode())
            digest = hashlib.md5(self._password.encode()).hexdigest()
            encrypted = public_key.encrypt(digest.encode(), padding.PKCS1v15()).hex()
            result = await self.request(
                "thing.m.user.email.password.login", "3.0",
                {
                    "countryCode": self._country_code,
                    "email": self._email,
                    "passwd": encrypted,
                    "options": '{"group": 1,"mfaCode": ""}',
                    "token": token["token"],
                    "ifencrypt": 1,
                },
            )
            if not isinstance(result, dict) or not result.get("sid"):
                raise MobileApiError("Login returned no SID")
            self.sid = result["sid"]
            if self._on_login is not None:
                await self._on_login(result)
            return result
        except Exception:
            self.sid = old_sid
            raise
