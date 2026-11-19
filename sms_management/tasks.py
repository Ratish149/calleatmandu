import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="sms_management.send_pending_sms_log",
    max_retries=3,
    default_retry_delay=60,
)
def send_pending_sms_log(self, sms_log_id: int):
    """
    Celery task: send a PENDING SMSLog via NestSMS.
    Scheduled with countdown when an order is delivered.
    """
    from sms_management.models import SMSLog
    from sms_management.services.order_sms_service import OrderSMSService

    sms_log = SMSLog.objects.filter(pk=sms_log_id).first()
    if not sms_log:
        logger.warning("SMSLog %s not found — skipping task.", sms_log_id)
        return {"status": "missing", "sms_log_id": sms_log_id}

    if sms_log.status != SMSLog.Status.PENDING:
        logger.info(
            "SMSLog %s status is %s — nothing to send.",
            sms_log_id,
            sms_log.status,
        )
        return {"status": sms_log.status, "sms_log_id": sms_log_id}

    updated = OrderSMSService.dispatch_sms_log(sms_log)
    return {
        "status": updated.status,
        "sms_log_id": sms_log_id,
        "job_id": updated.job_id,
    }
