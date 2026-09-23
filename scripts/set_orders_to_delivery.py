import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "calleatmandu.settings")

import django  # noqa: E402
django.setup()

from order.models import Order  # noqa: E402


def sync_order_types():
    total_orders = Order.objects.count()
    if total_orders == 0:
        print("No orders found in database.")
        return

    # If is_pos_order is True, set order_type to POS
    pos_updated = Order.objects.filter(is_pos_order=True).update(
        order_type=Order.OrderType.DINEIN
    )

    # Otherwise, set order_type to DELIVERY
    delivery_updated = Order.objects.filter(is_pos_order=False).update(
        order_type=Order.OrderType.DELIVERY
    )

    print(
        
        f"Successfully synced order types: "
        f"{pos_updated} order(s) set to 'POS', "
        f"{delivery_updated} order(s) set to 'DELIVERY' "
        f"(Total: {pos_updated + delivery_updated})."
    )


if __name__ == "__main__":
    sync_order_types()
