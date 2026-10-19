import logging

from celery import shared_task
from django.db import close_old_connections

logger = logging.getLogger(__name__)


@shared_task(
    name="marketplace.send_customer_notification_campaign",
    max_retries=0,
)
def send_customer_notification_campaign(campaign_id):
    """
    Send an existing notification campaign in the background.
    """

    close_old_connections()

    try:
        from .notification_service import process_notification_campaign

        result = process_notification_campaign(campaign_id)

        logger.info(
            "Notification campaign completed: %s",
            result,
        )

        return result

    except Exception:
        logger.exception(
            "Notification campaign failed. Campaign ID: %s",
            campaign_id,
        )
        raise

    finally:
        close_old_connections()


import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import NotificationJob

logger = logging.getLogger(__name__)


def process_next_notification_job():
    """
    Claim and process one pending notification job.
    """

    with transaction.atomic():
        job = (
            NotificationJob.objects
            .select_for_update(skip_locked=True)
            .filter(status="pending")
            .order_by("created_at")
            .first()
        )

        if job is None:
            return None

        job.status = "processing"
        job.started_at = timezone.now()
        job.attempts += 1
        job.error_message = ""

        job.save(
            update_fields=[
                "status",
                "started_at",
                "attempts",
                "error_message",
            ]
        )

        job_id = job.id

    try:
        from .notification_service import process_notification_campaign

        result = process_notification_campaign(
            NotificationJob.objects.get(pk=job_id).campaign_id
        )

        job = NotificationJob.objects.get(pk=job_id)
        job.status = "completed"
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

        logger.info(
            "Notification job %s completed: %s",
            job_id,
            result,
        )

        return result

    except Exception as exc:
        logger.exception(
            "Notification job %s failed.",
            job_id,
        )

        job = NotificationJob.objects.get(pk=job_id)
        job.status = "failed"
        job.error_message = str(exc)[:4000]
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "error_message",
                "completed_at",
            ]
        )

        return {
            "job_id": job_id,
            "status": "failed",
            "message": str(exc),
        }