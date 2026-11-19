"""Low-level NestSMS API client."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NestSMSError(Exception):
    """Raised when the NestSMS API returns an error or is misconfigured."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        payload: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.payload = payload or {}


class NestSMSService:
    """
    Service to send SMS and query status/balance via NestSMS.

    Auth: X-API-Key header (recommended by NestSMS).
    Config (settings / env):
      - NESTSMS_API_KEY
      - NESTSMS_BASE_URL  (default: https://auth.nestsms.com/api/v1/sms)
      - NESTSMS_SENDER_ID
      - NESTSMS_TIMEOUT_SECONDS
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sender_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings, "NESTSMS_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "NESTSMS_BASE_URL", "")).rstrip(
            "/"
        )
        # Empty = use NestSMS account default sender (recommended)
        configured = getattr(settings, "NESTSMS_SENDER_ID", "") or ""
        self.sender_id = (sender_id if sender_id is not None else configured).strip()
        self.timeout = timeout or getattr(settings, "NESTSMS_TIMEOUT_SECONDS", 30)

        if not self.api_key:
            raise NestSMSError(
                "NestSMS API key is missing. Set NESTSMS_API_KEY in settings/.env."
            )
        if not self.base_url:
            raise NestSMSError(
                "NestSMS base URL is missing. Set NESTSMS_BASE_URL in settings/.env."
            )

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self._headers,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.exception("NestSMS request failed: %s %s", method, url)
            raise NestSMSError(f"NestSMS request failed: {exc}") from exc

        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {"raw": response.text}

        if response.status_code >= 400 or payload.get("success") is False:
            error_msg = (
                payload.get("error")
                or payload.get("message")
                or f"NestSMS HTTP {response.status_code}"
            )
            logger.error(
                "NestSMS error %s %s → %s code=%s payload=%s",
                method,
                url,
                response.status_code,
                payload.get("code"),
                payload,
            )
            raise NestSMSError(
                message=str(error_msg),
                code=payload.get("code"),
                status_code=response.status_code,
                payload=payload,
            )

        return payload

    def send_sms(
        self,
        to: Union[str, List[str]],
        message: str,
        *,
        sender_id: Optional[str] = None,
        sms_type: str = "text",
        message_type: str = "transactional",
        template_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a single or bulk SMS via POST /send.

        Returns the NestSMS response payload (includes message_id / job_id).
        """
        resolved_sender = (sender_id if sender_id is not None else self.sender_id) or ""
        resolved_sender = resolved_sender.strip()
        # Placeholder / unassigned brand name — never send to NestSMS
        if resolved_sender.lower() in {"nestsms", "nest sms"}:
            resolved_sender = ""

        body: Dict[str, Any] = {
            "to": to,
            "type": sms_type,
            "message_type": message_type,
        }
        # Only send sender_id when explicitly configured — NestSMS rejects
        # unassigned IDs with SENDER_ID_NOT_ALLOWED.
        if resolved_sender:
            body["sender_id"] = resolved_sender

        if template_id:
            body["template_id"] = template_id
            if variables:
                body["variables"] = variables
        else:
            body["message"] = message

        logger.info(
            "Sending NestSMS url=%s/send to=%s sender_id=%s message_type=%s",
            self.base_url,
            to,
            resolved_sender or "(account default)",
            message_type,
        )
        return self._request("POST", "send", json_body=body)

    def get_balance(self) -> Dict[str, Any]:
        """GET /balance — wallet balance and usage stats."""
        return self._request("GET", "balance")

    def get_status(self, message_or_batch_id: str) -> Dict[str, Any]:
        """GET /status/:id — delivery status by message_id or batch_id."""
        return self._request("GET", f"status/{message_or_batch_id}")
