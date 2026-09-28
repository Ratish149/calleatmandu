import logging
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from account.models import Branch
from delivery.models import DeliveryPricing
from nps_payment.models import NPSConfig
from order.models import (
    ActivityLog,
    Order,
)
from order.services.activity_log_service import ActivityLogService
from product.models import Category, Product, ProductExtra, Subcategory

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Pre-save Snapshot Capture Utility
# ---------------------------------------------------------------------------


def _snapshot_instance(instance: Any) -> Dict[str, Any]:
    """Capture a lightweight field-value snapshot of a model instance prior to save."""
    snapshot: Dict[str, Any] = {}
    for field in instance._meta.fields:
        try:
            snapshot[field.name] = getattr(instance, field.attname)
        except Exception:
            continue
    return snapshot


@receiver(pre_save, sender=Order)
@receiver(pre_save, sender=Product)
@receiver(pre_save, sender=ProductExtra)
@receiver(pre_save, sender=Category)
@receiver(pre_save, sender=Subcategory)
@receiver(pre_save, sender=DeliveryPricing)
@receiver(pre_save, sender=NPSConfig)
@receiver(pre_save, sender=Branch)
def capture_model_pre_save_snapshot(sender, instance, **kwargs):
    """
    Saves an in-memory snapshot of the existing database record before changes are written,
    enabling precise field-level diff calculation in post_save.
    """
    if instance.pk:
        try:
            old_record = sender.objects.filter(pk=instance.pk).first()
            if old_record:
                instance._pre_save_snapshot = _snapshot_instance(old_record)
        except Exception as exc:
            logger.debug(
                "Could not capture pre_save snapshot for %s: %s", sender.__name__, exc
            )


# ---------------------------------------------------------------------------
# Existing Order WebSocket Handlers
# ---------------------------------------------------------------------------


# @receiver(post_save, sender=OrderStatusHistory)
# def handle_order_status_history_transition(
#     sender, instance: OrderStatusHistory, created: bool, **kwargs
# ):
#     """
#     Triggered whenever an OrderStatusHistory record is created.
#     If the status has changed to READY_FOR_PICKUP, broadcasts the complete order details
#     over the WebSocket after the database transaction successfully commits.
#     """
#     if created and instance.status == Order.OrderStatus.READY_FOR_PICKUP:
#         order_id = instance.order_id
#         transaction.on_commit(
#             lambda: OrderWebSocketService.broadcast_order_ready_for_pickup(order_id)
#         )


# @receiver(post_save, sender=Order)
# def handle_order_model_created(sender, instance: Order, created: bool, **kwargs):
#     """
#     Fallback receiver: If an Order is created outside OrderService (e.g. Django Admin or ORM script),
#     ensures it is broadcasted over WebSocket after transaction commit.
#     Orders created through OrderService set `_skip_signal_create = True` so items are fully attached first.
#     """
#     if created and not getattr(instance, "_skip_signal_create", False):
#         order_id = instance.id
#         transaction.on_commit(
#             lambda: OrderWebSocketService.broadcast_order_created(order_id)
#         )


# ---------------------------------------------------------------------------
# 1. Order Activity Logging (Single Unified Log per Operation)
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Order)
def handle_order_activity_post_save(sender, instance: Order, created: bool, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        item_changes = getattr(instance, "_order_item_changes", None)
        item_names = []
        if item_changes and item_changes.get("items_added"):
            item_names = item_changes["items_added"]

        items_summary = (
            f" with {len(item_names)} item(s) ({', '.join(item_names)})"
            if item_names
            else ""
        )
        changes_payload = {
            "order_number": instance.order_number,
            "status": instance.status,
            "order_type": instance.order_type,
            "payment_type": instance.payment_type,
            "total_amount": instance.total_amount,
            "customer_name": instance.customer_name,
            "phone_number": instance.phone_number,
        }
        if item_names:
            changes_payload["items"] = item_names

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.ORDER,
            entity_name="Order",
            record_id=str(instance.pk),
            record_repr=f"Order #{instance.order_number}",
            order=instance,
            description=(
                f"Order #{instance.order_number} created{items_summary} for customer "
                f"'{instance.customer_name or 'Walk-in'}' (Status: {instance.status}, "
                f"Type: {instance.order_type}, Total: Rs. {instance.total_amount})."
            ),
            changes=changes_payload,
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        field_changes = ActivityLogService.get_field_changes(snapshot, instance)
        item_changes = getattr(instance, "_order_item_changes", None)

        has_field_changes = bool(field_changes)
        has_item_changes = bool(
            item_changes
            and (
                item_changes.get("items_added")
                or item_changes.get("items_updated")
                or item_changes.get("items_removed")
            )
        )

        # Do not create spurious logs if nothing changed
        if not has_field_changes and not has_item_changes:
            return

        combined_changes = dict(field_changes)
        summary_parts = []

        if has_item_changes:
            added = item_changes.get("items_added", [])
            updated = item_changes.get("items_updated", [])
            removed = item_changes.get("items_removed", [])

            if added:
                combined_changes["items_added"] = added
                summary_parts.append(f"Added {len(added)} item(s) ({', '.join(added)})")
            if updated:
                combined_changes["items_updated"] = updated
                summary_parts.append(
                    f"Updated {len(updated)} item(s) ({', '.join(updated)})"
                )
            if removed:
                combined_changes["items_removed"] = removed
                summary_parts.append(
                    f"Removed {len(removed)} item(s) ({', '.join(removed)})"
                )

        if field_changes:
            field_summary = ActivityLogService.format_changes_summary(field_changes)
            if field_summary:
                summary_parts.append(field_summary)

        full_summary = "; ".join(summary_parts) if summary_parts else "Order updated"

        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.UPDATE,
            entity_type=ActivityLog.EntityType.ORDER,
            entity_name="Order",
            record_id=str(instance.pk),
            record_repr=f"Order #{instance.order_number}",
            order=instance,
            description=f"Order #{instance.order_number} updated: {full_summary}.",
            changes=combined_changes,
        )

        # Clear item changes from memory so any subsequent save in the same cycle does not duplicate
        if hasattr(instance, "_order_item_changes"):
            instance._order_item_changes = None


@receiver(post_delete, sender=Order)
def handle_order_activity_post_delete(sender, instance: Order, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.ORDER,
        entity_name="Order",
        record_id=str(instance.pk),
        record_repr=f"Order #{instance.order_number}",
        description=f"Order #{instance.order_number} was deleted.",
    )


# ---------------------------------------------------------------------------
# 2. Product Activity Logging (Product & ProductExtra)
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Product)
def handle_product_activity_post_save(
    sender, instance: Product, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.PRODUCT,
            entity_name="Product",
            record_id=str(instance.pk),
            record_repr=instance.name,
            description=f"Product '{instance.name}' created with price Rs. {instance.price}.",
            changes={
                "name": instance.name,
                "price": instance.price,
                "cost_price": instance.cost_price,
                "stock": instance.stock,
                "type": instance.type,
                "category": getattr(instance.category, "name", None),
            },
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.PRODUCT,
                entity_name="Product",
                record_id=str(instance.pk),
                record_repr=instance.name,
                description=f"Product '{instance.name}' updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=Product)
def handle_product_activity_post_delete(sender, instance: Product, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.PRODUCT,
        entity_name="Product",
        record_id=str(instance.pk),
        record_repr=instance.name,
        description=f"Product '{instance.name}' was deleted.",
    )


@receiver(post_save, sender=ProductExtra)
def handle_product_extra_activity_post_save(
    sender, instance: ProductExtra, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    product_name = getattr(instance.product, "name", f"Product #{instance.product_id}")
    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.PRODUCT,
            entity_name="ProductExtra",
            record_id=str(instance.pk),
            record_repr=f"{instance.name} ({product_name})",
            description=f"Product extra '{instance.name}' (+Rs. {instance.additional_price}) created for '{product_name}'.",
            changes={
                "name": instance.name,
                "additional_price": instance.additional_price,
                "product": product_name,
            },
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.PRODUCT,
                entity_name="ProductExtra",
                record_id=str(instance.pk),
                record_repr=f"{instance.name} ({product_name})",
                description=f"Product extra '{instance.name}' updated for '{product_name}': {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=ProductExtra)
def handle_product_extra_activity_post_delete(sender, instance: ProductExtra, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    product_name = getattr(instance.product, "name", f"Product #{instance.product_id}")
    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.PRODUCT,
        entity_name="ProductExtra",
        record_id=str(instance.pk),
        record_repr=f"{instance.name} ({product_name})",
        description=f"Product extra '{instance.name}' removed from '{product_name}'.",
    )


# ---------------------------------------------------------------------------
# 4. Category Activity Logging (Category & Subcategory)
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Category)
def handle_category_activity_post_save(
    sender, instance: Category, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.CATEGORY,
            entity_name="Category",
            record_id=str(instance.pk),
            record_repr=instance.name,
            description=f"Category '{instance.name}' created.",
            changes={"name": instance.name, "slug": instance.slug},
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.CATEGORY,
                entity_name="Category",
                record_id=str(instance.pk),
                record_repr=instance.name,
                description=f"Category '{instance.name}' updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=Category)
def handle_category_activity_post_delete(sender, instance: Category, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.CATEGORY,
        entity_name="Category",
        record_id=str(instance.pk),
        record_repr=instance.name,
        description=f"Category '{instance.name}' was deleted.",
    )


@receiver(post_save, sender=Subcategory)
def handle_subcategory_activity_post_save(
    sender, instance: Subcategory, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    parent_cat = getattr(instance.category, "name", "None")
    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.CATEGORY,
            entity_name="Subcategory",
            record_id=str(instance.pk),
            record_repr=f"{instance.name} ({parent_cat})",
            description=f"Subcategory '{instance.name}' created under '{parent_cat}'.",
            changes={"name": instance.name, "category": parent_cat},
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.CATEGORY,
                entity_name="Subcategory",
                record_id=str(instance.pk),
                record_repr=f"{instance.name} ({parent_cat})",
                description=f"Subcategory '{instance.name}' updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=Subcategory)
def handle_subcategory_activity_post_delete(sender, instance: Subcategory, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    parent_cat = getattr(instance.category, "name", "None")
    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.CATEGORY,
        entity_name="Subcategory",
        record_id=str(instance.pk),
        record_repr=f"{instance.name} ({parent_cat})",
        description=f"Subcategory '{instance.name}' was deleted.",
    )


# ---------------------------------------------------------------------------
# 5. User Activity Logging ("user created")
# ---------------------------------------------------------------------------


@receiver(post_save, sender=User)
def handle_user_activity_post_save(sender, instance, created: bool, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        role = getattr(instance, "role", "customer")
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.USER,
            entity_name="User",
            record_id=str(instance.pk),
            record_repr=instance.username,
            description=f"New user '{instance.username}' created with role '{role}'.",
            changes={
                "username": instance.username,
                "role": role,
                "email": instance.email,
                "phone_number": getattr(instance, "phone_number", None),
            },
        )


# ---------------------------------------------------------------------------
# 6. Setting Changes Logging (DeliveryPricing, NPSConfig, Branch)
# ---------------------------------------------------------------------------


@receiver(post_save, sender=DeliveryPricing)
def handle_delivery_pricing_activity_post_save(
    sender, instance: DeliveryPricing, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.SETTING,
            entity_name="DeliveryPricing",
            record_id=str(instance.pk),
            record_repr=str(instance),
            description=(
                f"Delivery pricing setting created: Rs. {instance.price_per_km}/km "
                f"(Base: Rs. {instance.minimum_charge}, Active: {instance.is_active})."
            ),
            changes={
                "price_per_km": instance.price_per_km,
                "minimum_charge": instance.minimum_charge,
                "is_active": instance.is_active,
            },
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.SETTING,
                entity_name="DeliveryPricing",
                record_id=str(instance.pk),
                record_repr=str(instance),
                description=f"Delivery pricing setting updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=DeliveryPricing)
def handle_delivery_pricing_activity_post_delete(
    sender, instance: DeliveryPricing, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.SETTING,
        entity_name="DeliveryPricing",
        record_id=str(instance.pk),
        record_repr=str(instance),
        description="Delivery pricing setting was deleted.",
    )


@receiver(post_save, sender=NPSConfig)
def handle_nps_config_activity_post_save(
    sender, instance: NPSConfig, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.SETTING,
            entity_name="NPSConfig",
            record_id=str(instance.pk),
            record_repr=instance.merchant_name,
            description=f"NPS payment configuration created for merchant '{instance.merchant_name}'.",
            changes={
                "merchant_id": instance.merchant_id,
                "merchant_name": instance.merchant_name,
                "is_sandbox": instance.is_sandbox,
                "is_enabled": instance.is_enabled,
            },
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(
            snapshot, instance, exclude_fields={"api_password", "secret_key"}
        )
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.SETTING,
                entity_name="NPSConfig",
                record_id=str(instance.pk),
                record_repr=instance.merchant_name,
                description=f"NPS payment configuration updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=NPSConfig)
def handle_nps_config_activity_post_delete(sender, instance: NPSConfig, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.SETTING,
        entity_name="NPSConfig",
        record_id=str(instance.pk),
        record_repr=instance.merchant_name,
        description=f"NPS payment configuration '{instance.merchant_name}' was deleted.",
    )


@receiver(post_save, sender=Branch)
def handle_branch_setting_activity_post_save(
    sender, instance: Branch, created: bool, **kwargs
):
    if getattr(instance, "_skip_activity_log", False):
        return

    if created:
        ActivityLogService.log_activity(
            action_type=ActivityLog.ActionType.CREATE,
            entity_type=ActivityLog.EntityType.SETTING,
            entity_name="Branch",
            record_id=str(instance.pk),
            record_repr=instance.name,
            description=f"Branch setting created: '{instance.name}' at {instance.address}.",
            changes={
                "name": instance.name,
                "address": instance.address,
                "phone": instance.phone,
                "maximum_delivery_distance_km": instance.maximum_delivery_distance_km,
            },
        )
    else:
        snapshot = getattr(instance, "_pre_save_snapshot", None)
        changes = ActivityLogService.get_field_changes(snapshot, instance)
        if changes:
            summary = ActivityLogService.format_changes_summary(changes)
            ActivityLogService.log_activity(
                action_type=ActivityLog.ActionType.UPDATE,
                entity_type=ActivityLog.EntityType.SETTING,
                entity_name="Branch",
                record_id=str(instance.pk),
                record_repr=instance.name,
                description=f"Branch '{instance.name}' setting updated: {summary}.",
                changes=changes,
            )


@receiver(post_delete, sender=Branch)
def handle_branch_setting_activity_post_delete(sender, instance: Branch, **kwargs):
    if getattr(instance, "_skip_activity_log", False):
        return

    ActivityLogService.log_activity(
        action_type=ActivityLog.ActionType.DELETE,
        entity_type=ActivityLog.EntityType.SETTING,
        entity_name="Branch",
        record_id=str(instance.pk),
        record_repr=instance.name,
        description=f"Branch setting '{instance.name}' was deleted.",
    )
