import base64
import hashlib
import hmac
import uuid
from typing import Any, Dict, Tuple

import requests

from ..constants import (
    ENDPOINT_CHECK_STATUS,
    ENDPOINT_GET_INSTRUMENTS,
    ENDPOINT_GET_PROCESS_ID,
    ENDPOINT_GET_SERVICE_CHARGE,
    NPS_PRODUCTION_BASE_URL,
    NPS_PRODUCTION_GATEWAY_URL,
    NPS_SANDBOX_BASE_URL,
    NPS_SANDBOX_GATEWAY_URL,
)
from ..models import NPSConfig


def generate_hmac_sha512(payload: Dict[str, Any], secret_key: str) -> str:
    """
    Generates HMAC-SHA512 hex signature:
    1. Sort keys alphabetically
    2. Concatenate non-empty values
    3. Apply HMAC-SHA512 with secret_key
    """
    sorted_keys = sorted(payload.keys())
    concatenated_values = "".join(
        str(payload[k])
        for k in sorted_keys
        if payload[k] is not None and payload[k] != ""
    )
    hash_obj = hmac.new(
        secret_key.encode("utf-8"),
        concatenated_values.encode("utf-8"),
        hashlib.sha512,
    )
    return hash_obj.hexdigest().lower()


def get_basic_auth_header(username: str, password: str) -> Dict[str, str]:
    """Generates Basic Auth header dict."""
    user_pass = f"{username}:{password}"
    b64_encoded = base64.b64encode(user_pass.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_encoded}",
        "Content-Type": "application/json",
    }


def get_nps_base_url(config: NPSConfig) -> str:
    return NPS_SANDBOX_BASE_URL if config.is_sandbox else NPS_PRODUCTION_BASE_URL


def get_nps_gateway_url(config: NPSConfig) -> str:
    return NPS_SANDBOX_GATEWAY_URL if config.is_sandbox else NPS_PRODUCTION_GATEWAY_URL


def generate_merchant_txn_id() -> str:
    return f"NPS-TXN-{uuid.uuid4().hex[:12].upper()}"


def fetch_payment_instruments(config: NPSConfig) -> Dict[str, Any]:
    url = f"{get_nps_base_url(config)}{ENDPOINT_GET_INSTRUMENTS}"
    payload = {
        "MerchantId": config.merchant_id,
        "MerchantName": config.merchant_name,
    }
    payload["Signature"] = generate_hmac_sha512(payload, config.secret_key)
    headers = get_basic_auth_header(config.api_username, config.api_password)

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    return response.json()


def fetch_service_charge(
    config: NPSConfig, amount: str, instrument_code: str
) -> Dict[str, Any]:
    url = f"{get_nps_base_url(config)}{ENDPOINT_GET_SERVICE_CHARGE}"
    payload = {
        "MerchantId": config.merchant_id,
        "MerchantName": config.merchant_name,
        "Amount": str(amount),
        "InstrumentCode": instrument_code,
    }
    payload["Signature"] = generate_hmac_sha512(payload, config.secret_key)
    headers = get_basic_auth_header(config.api_username, config.api_password)

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    return response.json()


def get_process_id(
    config: NPSConfig, amount: str, merchant_txn_id: str
) -> Tuple[bool, Dict[str, Any]]:
    base_url = get_nps_base_url(config)
    url = f"{base_url}{ENDPOINT_GET_PROCESS_ID}"

    payload = {
        "MerchantId": config.merchant_id,
        "MerchantName": config.merchant_name,
        "Amount": str(amount),
        "MerchantTxnId": merchant_txn_id,
    }
    payload["Signature"] = generate_hmac_sha512(payload, config.secret_key)
    headers = get_basic_auth_header(config.api_username, config.api_password)

    print("\n================ [NPS GetProcessId Request] ================")
    print(
        f"Environment Mode: {'Sandbox' if config.is_sandbox else 'PRODUCTION (Live)'}"
    )
    print(f"Target API URL: {url}")
    print(f"Payload: {payload}")
    print(f"Headers: {headers}")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"HTTP Status: {response.status_code}")
        print(f"Raw Response: {response.text}")
        print("===========================================================\n")

        if response.status_code == 200:
            res_data = response.json()
            success = str(res_data.get("code")) == "0"
            res_data["target_gateway_url"] = get_nps_gateway_url(config)
            return success, res_data
        else:
            return False, {
                "code": "1",
                "message": f"HTTP {response.status_code}: {response.text}",
            }
    except Exception as e:
        print(f"Connection Exception on {url}: {e}")
        print("===========================================================\n")
        raise e


def verify_transaction_status(
    config: NPSConfig, merchant_txn_id: str
) -> Tuple[bool, Dict[str, Any]]:
    url = f"{get_nps_base_url(config)}{ENDPOINT_CHECK_STATUS}"
    payload = {
        "MerchantId": config.merchant_id,
        "MerchantName": config.merchant_name,
        "MerchantTxnId": merchant_txn_id,
    }
    payload["Signature"] = generate_hmac_sha512(payload, config.secret_key)
    headers = get_basic_auth_header(config.api_username, config.api_password)

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    res_data = response.json()

    success = res_data.get("code") == "0"
    return success, res_data


def build_gateway_form_payload(
    config: NPSConfig,
    merchant_txn_id: str,
    amount: str,
    process_id: str,
    remarks: str = "",
    instrument_code: str = "",
    response_url: str = "",
    override_gateway_url: str = "",
) -> Dict[str, Any]:
    gateway_url = override_gateway_url or get_nps_gateway_url(config)
    form_fields = {
        "MerchantId": config.merchant_id,
        "MerchantName": config.merchant_name,
        "MerchantTxnId": merchant_txn_id,
        "Amount": str(amount),
        "ProcessId": process_id,
        "InstrumentCode": instrument_code or "",
        "TransactionRemarks": remarks or "Order Checkout",
        "ResponseUrl": response_url or "",
    }
    print("================ [NPS Gateway Form Payload] ================")
    print(f"Action Gateway URL: {gateway_url}")
    print(f"Form Fields: {form_fields}")
    print("===========================================================\n")
    return {
        "action_url": gateway_url,
        "method": "POST",
        "enctype": "multipart/form-data",
        "form_fields": form_fields,
    }
