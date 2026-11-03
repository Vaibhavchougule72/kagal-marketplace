import logging

from celery import shared_task
from django.db import close_old_connections

logger = logging.getLogger(__name__)

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

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

@shared_task(
    name="marketplace.process_rider_offer_reminder",
    max_retries=0,
)
def process_rider_offer_reminder(offer_id):

    close_old_connections()

    try:
        from .models import (
            RiderOrderOffer,
            DeliveryPartnerProfile,
        )
        from .firebase import send_rider_new_order_notification
        from .rider_dispatch_service import (
            dispatch_order_to_next_rider,
        )

        # Fetch the offer
        with transaction.atomic():

            offer = (
                RiderOrderOffer.objects
                .select_for_update()
                .select_related("order", "rider")
                .filter(pk=offer_id)
                .first()
            )

            if offer is None or offer.status != "PENDING":
                return "Offer is no longer pending."

            order = offer.order

            # Stop if order is already assigned or no longer awaiting a rider
            if (
                order.assigned_delivery_id
                or order.status not in ["REQUEST_SUBMITTED", "ACCEPTED"]
            ):
                offer.status = "EXPIRED"
                offer.next_notification_at = None
                offer.save(
                    update_fields=["status", "next_notification_at"]
                )
                return "Order is already assigned or closed."

            # Check whether rider is still eligible
            rider_profile = DeliveryPartnerProfile.objects.filter(
                user=offer.rider,
                is_active=True,
                is_available=True,
            ).first()

            if rider_profile is None:
                offer.status = "ESCALATED"
                offer.escalated_at = timezone.now()
                offer.next_notification_at = None
                offer.save(
                    update_fields=[
                        "status",
                        "escalated_at",
                        "next_notification_at",
                    ]
                )

                move_to_next_rider = True

            elif offer.notification_count >= 3:
                offer.status = "ESCALATED"
                offer.escalated_at = timezone.now()
                offer.next_notification_at = None
                offer.save(
                    update_fields=[
                        "status",
                        "escalated_at",
                        "next_notification_at",
                    ]
                )

                move_to_next_rider = True

            else:
                move_to_next_rider = False

        # If the rider is offline or has not responded after 3 notifications
        if move_to_next_rider:
            dispatch_order_to_next_rider(order)
            return "Offer escalated. Next rider notified."

        # Send the next reminder
        from .models import RiderDeviceToken

        tokens = RiderDeviceToken.objects.filter(
            user=offer.rider,
            is_active=True,
        )

        sent_count = 0

        for device in tokens:
            try:
                send_rider_new_order_notification(
                    token=device.token,
                    order=order,
                    offer=offer,
                )
                sent_count += 1

            except Exception:
                logger.exception(
                    "Rider reminder failed. Offer ID: %s",
                    offer_id,
                )

        if sent_count == 0:
            with transaction.atomic():
                offer = RiderOrderOffer.objects.select_for_update().get(
                    pk=offer_id
                )

                if offer.status == "PENDING":
                    offer.status = "ESCALATED"
                    offer.escalated_at = timezone.now()
                    offer.next_notification_at = None
                    offer.save(
                        update_fields=[
                            "status",
                            "escalated_at",
                            "next_notification_at",
                        ]
                    )

            dispatch_order_to_next_rider(order)
            return "Reminder failed. Offer escalated."

        # Update notification count and schedule the next reminder
        with transaction.atomic():

            offer = RiderOrderOffer.objects.select_for_update().get(
                pk=offer_id
            )

            if offer.status != "PENDING":
                return "Offer was already handled."

            now = timezone.now()

            offer.notification_count += 1
            offer.last_notified_at = now

            # After reminder 2, wait another 2 minutes.
            # After reminder 3, wait 2 minutes before escalation.
            offer.next_notification_at = now + timedelta(minutes=2)

            offer.save(
                update_fields=[
                    "notification_count",
                    "last_notified_at",
                    "next_notification_at",
                ]
            )

            next_delay = 120

        process_rider_offer_reminder.apply_async(
            args=[offer_id],
            countdown=next_delay,
        )

        return "Rider reminder sent."

    except Exception:
        logger.exception(
            "Rider reminder task failed. Offer ID: %s",
            offer_id,
        )
        raise

    finally:
        close_old_connections()