"""Trigger NestSMS when an order status changes to DELIVERED."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from order.models import Order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def send_sms_on_order_delivered(sender, instance: Order, created: bool, **kwargs):
    """
    When an order transitions to DELIVERED, schedule a post-delivery SMS
    only if the order's branch has SMS settings with is_enabled=True.
    """
    if created:
        return

    snapshot = getattr(instance, "_pre_save_snapshot", None)
    if not snapshot:
        return

    old_status = snapshot.get("status")
    new_status = instance.status

    if old_status == new_status:
        return

    if new_status != Order.OrderStatus.DELIVERED:
        return

    branch = getattr(instance, "branch", None)
    if not branch:
        logger.info(
            "Order %s has no branch — skipping SMS log creation.",
            instance.order_number,
        )
        return

    from sms_management.models import SMSSettings

    sms_settings = SMSSettings.get_for_branch(branch)
    if not sms_settings or not sms_settings.is_enabled:
        logger.info(
            "SMS not enabled for branch %s — skipping SMS log for order %s.",
            getattr(branch, "name", branch.pk),
            instance.order_number,
        )
        return

    from sms_management.services.order_sms_service import OrderSMSService

    OrderSMSService.trigger_on_commit(instance.pk)
