import os

from dotenv import load_dotenv

load_dotenv()
# NPS / OnePG Gateway Endpoints & Constants

NPS_SANDBOX_BASE_URL = os.getenv(
    "NPS_SANDBOX_BASE_URL", "https://apisandbox.nepalpayment.com"
)
NPS_PRODUCTION_BASE_URL = os.getenv(
    "NPS_PRODUCTION_BASE_URL", "https://apisandbox.nepalpayment.com"
)

NPS_SANDBOX_GATEWAY_URL = os.getenv(
    "NPS_SANDBOX_GATEWAY_URL", "https://gatewaysandbox.nepalpayment.com/Payment/Index"
)
NPS_PRODUCTION_GATEWAY_URL = os.getenv(
    "NPS_PRODUCTION_GATEWAY_URL",
    "https://gatewaysandbox.nepalpayment.com/Payment/Index",
)

ENDPOINT_GET_INSTRUMENTS = "/GetPaymentInstrumentDetails"
ENDPOINT_GET_SERVICE_CHARGE = "/GetServiceCharge"
ENDPOINT_GET_PROCESS_ID = "/GetProcessId"
ENDPOINT_CHECK_STATUS = "/CheckTransactionStatus"

TRANSACTION_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Success", "Success"),
    ("Fail", "Fail"),
)
