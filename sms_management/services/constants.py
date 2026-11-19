"""NestSMS configuration defaults and SMS message template."""

import os

from dotenv import load_dotenv

load_dotenv()

NESTSMS_API_KEY = os.getenv("NESTSMS_API_KEY", "")
NESTSMS_BASE_URL = os.getenv(
    "NESTSMS_BASE_URL", "https://auth.nestsms.com/api/v1/sms"
).rstrip("/")
NESTSMS_SENDER_ID = os.getenv("NESTSMS_SENDER_ID", "")
NESTSMS_TIMEOUT_SECONDS = int(os.getenv("NESTSMS_TIMEOUT_SECONDS", "30"))

POST_DELIVERY_SMS_DELAY_MINUTES = int(
    os.getenv("POST_DELIVERY_SMS_DELAY_MINUTES", "30")
)

POST_DELIVERY_SMS_TEMPLATE = os.getenv(
    "POST_DELIVERY_SMS_TEMPLATE",
    "Dear {customer_name}, how was your CallEatMandu order #{order_number}? "
    "We hope you enjoyed your meal. Thank you!",
)
