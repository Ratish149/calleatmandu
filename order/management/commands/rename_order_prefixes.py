from django.core.management.base import BaseCommand
from django.db import transaction

from order.models import Order


class Command(BaseCommand):
    help = "Renames all order numbers starting with EAT_ to ORD_"

    def handle(self, *args, **options):
        orders = Order.objects.filter(order_number__startswith="EAT_")
        total = orders.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No orders found with prefix 'EAT_'."))
            return

        updated_count = 0
        with transaction.atomic():
            for order in orders:
                old_number = order.order_number
                new_number = "ORD_" + old_number[4:]
                order.order_number = new_number
                order.save(update_fields=["order_number"])
                updated_count += 1
                self.stdout.write(f"Updated {old_number} -> {new_number}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_count} order(s) from 'EAT_' to 'ORD_'."
            )
        )
