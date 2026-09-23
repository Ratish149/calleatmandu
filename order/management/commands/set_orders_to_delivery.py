from django.core.management.base import BaseCommand

from order.models import Order


class Command(BaseCommand):
    help = "Updates orders based on is_pos_order: True -> POS, False -> DELIVERY"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-null",
            action="store_true",
            help="Only update orders where order_type is currently NULL",
        )

    def handle(self, *args, **options):
        only_null = options.get("only_null", False)

        base_qs = (
            Order.objects.filter(order_type__isnull=True)
            if only_null
            else Order.objects.all()
        )

        total = base_qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No orders found to update."))
            return

        # If is_pos_order is True, set order_type to POS
        pos_updated = base_qs.filter(is_pos_order=True).update(
            order_type=Order.OrderType.DINEIN
        )

        # Otherwise, set order_type to DELIVERY
        delivery_updated = base_qs.filter(is_pos_order=False).update(
            order_type=Order.OrderType.DELIVERY
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated order types: "
                f"{pos_updated} order(s) set to 'POS', "
                f"{delivery_updated} order(s) set to 'DELIVERY' "
                f"(Total: {pos_updated + delivery_updated})."
            )
        )
