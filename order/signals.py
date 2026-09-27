import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from order.models import Order, OrderStatusHistory
from order.services.order_websocket_service import OrderWebSocketService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OrderStatusHistory)
def handle_order_status_history_transition(
    sender, instance: OrderStatusHistory, created: bool, **kwargs
):
    """
    Triggered whenever an OrderStatusHistory record is created.
    If the status has changed to READY_FOR_PICKUP, broadcasts the complete order details
    over the WebSocket after the database transaction successfully commits.
    """
    if created and instance.status == Order.OrderStatus.READY_FOR_PICKUP:
        order_id = instance.order_id
        transaction.on_commit(
            lambda: OrderWebSocketService.broadcast_order_ready_for_pickup(order_id)
        )


@receiver(post_save, sender=Order)
def handle_order_model_created(
    sender, instance: Order, created: bool, **kwargs
):
    """
    Fallback receiver: If an Order is created outside OrderService (e.g. Django Admin or ORM script),
    ensures it is broadcasted over WebSocket after transaction commit.
    Orders created through OrderService set `_skip_signal_create = True` so items are fully attached first.
    """
    if created and not getattr(instance, "_skip_signal_create", False):
        order_id = instance.id
        transaction.on_commit(
            lambda: OrderWebSocketService.broadcast_order_created(order_id)
        )
