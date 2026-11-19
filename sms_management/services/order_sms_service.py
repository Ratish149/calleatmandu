"""Schedule and send SMS 30 minutes after an order is delivered via Celery."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from order.services.order_export_service import OrderExportService
from sms_management.models import SMSLog, SMSSettings
from sms_management.services.nestsms_service import NestSMSError, NestSMSService

logger = logging.getLogger(__name__)


class OrderSMSService:
    """
    When an order is delivered, creates a PENDING SMSLog and enqueues a
    Celery task using that order's branch SMSSettings (if enabled).
    """

    @classmethod
    def handle_order_delivered(cls, order) -> Optional[SMSLog]:
        """
        Entry point after an order transitions to DELIVERED.
        Creates a scheduled SMS log and enqueues Celery task (idempotent).
        Only runs when the order's branch has enabled SMS settings.
        """
        branch = getattr(order, "branch", None)
        if not branch:
            logger.info(
                "Order %s has no branch — skipping post-delivery SMS.",
                getattr(order, "order_number", order.pk),
            )
            return None

        sms_settings = SMSSettings.get_for_branch(branch)
        if not sms_settings:
            logger.info(
                "No SMS settings for branch %s — skipping order %s.",
                getattr(branch, "name", branch.pk),
                getattr(order, "order_number", order.pk),
            )
            return None

        if not sms_settings.is_enabled:
            logger.info(
                "SMS disabled for branch %s — skipping order %s.",
                getattr(branch, "name", branch.pk),
                getattr(order, "order_number", order.pk),
            )
            return None

        phone = OrderExportService.clean_phone_number(
            getattr(order, "phone_number", None)
        )
        if not phone:
            logger.warning(
                "Skipping post-delivery SMS for order %s — invalid/missing phone.",
                getattr(order, "order_number", order.pk),
            )
            return None

        existing = SMSLog.objects.filter(
            order=order,
            status__in=[SMSLog.Status.PENDING, SMSLog.Status.SENT],
        ).first()
        if existing:
            if existing.status == SMSLog.Status.SENT:
                logger.info(
                    "Post-delivery SMS already sent for order %s — skipping.",
                    order.order_number,
                )
                return existing

            # PENDING but enqueue may have failed earlier (e.g. Redis down) — re-queue
            countdown = 0
            if existing.scheduled_at:
                countdown = max(
                    0,
                    int((existing.scheduled_at - timezone.now()).total_seconds()),
                )
            cls.enqueue_sms_log(existing, countdown=countdown)
            logger.info(
                "Re-enqueued pending SMS for order %s in %ss (sms_log=%s).",
                order.order_number,
                countdown,
                existing.pk,
            )
            return existing

        delay_minutes = int(sms_settings.delay_minutes or 30)
        delay_seconds = max(0, delay_minutes * 60)
        scheduled_at = timezone.now() + timedelta(seconds=delay_seconds)
        template = (
            (sms_settings.message_template or "").strip()
            or SMSSettings.DEFAULT_MESSAGE
        )
        message = cls._render_template(template, order)
        sms_log = SMSLog.objects.create(
            order=order,
            branch=branch,
            status=SMSLog.Status.PENDING,
            phone_number=phone,
            message=message,
            scheduled_at=scheduled_at,
        )
        cls.enqueue_sms_log(sms_log, countdown=delay_seconds)
        logger.info(
            "Enqueued post-delivery SMS for order %s (branch=%s) in %ss (sms_log=%s).",
            order.order_number,
            getattr(branch, "name", branch.pk),
            delay_seconds,
            sms_log.pk,
        )
        return sms_log

    @classmethod
    def enqueue_sms_log(cls, sms_log: SMSLog, countdown: int) -> None:
        """Enqueue Celery task to send this SMSLog after `countdown` seconds."""
        from sms_management.tasks import send_pending_sms_log

        send_pending_sms_log.apply_async(
            args=[sms_log.pk],
            countdown=max(0, int(countdown)),
            ignore_result=True,
        )

    @classmethod
    def _customer_name(cls, order) -> str:
        name = (getattr(order, "customer_name", None) or "").strip()
        return name or "Customer"

    @classmethod
    def _render_template(cls, template: str, order) -> str:
        values = {
            "customer_name": cls._customer_name(order),
            "order_number": str(getattr(order, "order_number", order.pk)),
        }
        try:
            return template.format(**values)
        except (KeyError, ValueError, IndexError):
            # Admin used unknown placeholders — fall back to simple replace
            rendered = template
            for key, value in values.items():
                rendered = rendered.replace("{" + key + "}", value)
            return rendered

    @classmethod
    def dispatch_sms_log(cls, sms_log: SMSLog) -> SMSLog:
        """Send a PENDING SMSLog via NestSMS and update its status."""
        if sms_log.status == SMSLog.Status.SENT:
            return sms_log

        try:
            # Always omit sender_id — NestSMS uses the account default
            service = NestSMSService()
            result = service.send_sms(
                to=sms_log.phone_number,
                message=sms_log.message,
                sender_id="",
                message_type="transactional",
            )
        except NestSMSError as exc:
            sms_log.status = SMSLog.Status.FAILED
            sms_log.error_message = str(exc)
            sms_log.response_payload = getattr(exc, "payload", {}) or {}
            sms_log.save(
                update_fields=[
                    "status",
                    "error_message",
                    "response_payload",
                    "updated_at",
                ]
            )
            logger.error("Failed to send SMS log %s: %s", sms_log.pk, exc)
            return sms_log
        except Exception as exc:  # noqa: BLE001 — never break order flow
            sms_log.status = SMSLog.Status.FAILED
            sms_log.error_message = str(exc)
            sms_log.save(update_fields=["status", "error_message", "updated_at"])
            logger.exception("Unexpected error sending SMS log %s", sms_log.pk)
            return sms_log

        data = result.get("data") or {}
        # Prefer message_id for delivery tracking (job_id is only queue metadata)
        tracking_id = (
            data.get("message_id")
            or (data.get("message_ids") or [None])[0]
            or data.get("batch_id")
            or data.get("job_id")
            or ""
        )
        if not tracking_id and data.get("job_ids"):
            job_ids = data["job_ids"]
            tracking_id = job_ids[0] if job_ids else ""

        sms_log.status = SMSLog.Status.SENT
        sms_log.sent_at = timezone.now()
        sms_log.job_id = str(tracking_id)
        sms_log.cost = data.get("cost") or data.get("total_cost")
        sms_log.response_payload = result
        sms_log.error_message = ""
        sms_log.save(
            update_fields=[
                "status",
                "sent_at",
                "job_id",
                "cost",
                "response_payload",
                "error_message",
                "updated_at",
            ]
        )
        logger.info(
            "Sent SMS log %s (job_id=%s) to %s",
            sms_log.pk,
            sms_log.job_id,
            sms_log.phone_number,
        )
        return sms_log

    @classmethod
    def trigger_on_commit(cls, order_id: int) -> None:
        """Load order after commit and schedule post-delivery SMS."""

        def _run():
            from order.models import Order

            order = Order.objects.filter(pk=order_id).first()
            if not order:
                return
            try:
                cls.handle_order_delivered(order)
            except Exception:  # noqa: BLE001 — never break order save
                logger.exception(
                    "Failed scheduling post-delivery SMS for order id=%s",
                    order_id,
                )

        transaction.on_commit(_run)
