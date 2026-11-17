import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "calleatmandu.settings")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402
from accounting.models import VendorTransaction  # noqa: E402


def update_vendor_payment_methods():
    """
    Normalizes payment methods for all VendorTransaction records:
    - If already 'CASH' (case-insensitive), retains 'CASH'.
    - If any other payment method (or NULL/empty), updates to 'ONLINE'.
    """
    total_count = VendorTransaction.objects.count()
    if total_count == 0:
        print("No VendorTransaction records found in the database.")
        return

    print(f"Found {total_count} VendorTransaction record(s) in the database.")

    with transaction.atomic():
        # Ensure any existing 'cash' variation is standardized to 'CASH'
        cash_qs = VendorTransaction.objects.filter(
            payment_method__iexact=VendorTransaction.PaymentMethod.CASH
        )
        cash_count = cash_qs.count()
        cash_qs.exclude(payment_method=VendorTransaction.PaymentMethod.CASH).update(
            payment_method=VendorTransaction.PaymentMethod.CASH
        )

        # Update all non-cash payment methods to 'ONLINE'
        non_cash_qs = VendorTransaction.objects.exclude(
            payment_method__iexact=VendorTransaction.PaymentMethod.CASH
        )
        non_cash_count = non_cash_qs.count()
        updated_count = non_cash_qs.update(
            payment_method=VendorTransaction.PaymentMethod.ONLINE
        )

    print("\n--- Summary of Updates ---")
    print(f"Total records processed : {total_count}")
    print(f"Retained as CASH        : {cash_count}")
    print(f"Updated to ONLINE       : {updated_count} (out of {non_cash_count} non-cash records)")
    print("Vendor transaction payment methods successfully normalized.")


if __name__ == "__main__":
    update_vendor_payment_methods()
