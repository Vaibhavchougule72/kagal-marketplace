import logging

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from marketplace.models import (
    BehaviouralNotification,
    CustomerActivity,
    DeviceToken,
)

from marketplace.firebase import send_push_notification

logger = logging.getLogger(__name__)


# =====================================================
# WORKER SETTINGS
# =====================================================

BATCH_SIZE = 20

INACTIVITY_GRACE_MINUTES = 2

PROCESSING_TIMEOUT_MINUTES = 10


# =====================================================
# CHECK WHETHER CUSTOMER IS INACTIVE
# =====================================================

def customer_is_inactive(notification):

    session = notification.session

    now = timezone.now()

    last_ping = session.last_ping_at

    # If there is a recent heartbeat, customer may
    # still be using LOKA.
    if last_ping:

        inactivity_limit = now - timedelta(
            minutes=INACTIVITY_GRACE_MINUTES
        )

        if last_ping > inactivity_limit:
            return False

    return True


# =====================================================
# VALIDATE NOTIFICATION
# =====================================================

def validate_notification(notification):

    session = notification.session

    # 1. Check whether an order was placed.
    order_exists = CustomerActivity.objects.filter(
        session=session,
        event_type="ORDER_PLACED"
    ).exists()

    if order_exists:
        return False, "Customer already placed an order."

    # 2. Check whether a newer activity occurred.
    if notification.activity_id:

        newer_activity = CustomerActivity.objects.filter(
            session=session,
            created_at__gt=notification.activity.created_at
        ).exists()

        if newer_activity:
            return False, "A newer customer activity was recorded."

    # 3. Check customer account.
    if not notification.customer.is_active:
        return False, "Customer account is inactive."

    # 4. Check inactivity.
    if not customer_is_inactive(notification):
        return False, "Customer is still active."

    # 5. Check registered device.
    tokens_exist = DeviceToken.objects.filter(
        phone=notification.customer.phone
    ).exists()

    if not tokens_exist:
        return False, "No registered device token."

    return True, ""


# =====================================================
# CLAIM NEXT NOTIFICATION
# =====================================================

def claim_next_notification():

    now = timezone.now()

    with transaction.atomic():

        # Recover notifications stuck in PROCESSING.
        stale_processing = (
            BehaviouralNotification.objects.filter(
                status="PROCESSING",
                locked_at__lt=now - timedelta(
                    minutes=PROCESSING_TIMEOUT_MINUTES
                )
            )
        )

        stale_processing.update(
            status="PENDING",
            locked_at=None,
            error_message="Recovered after worker interruption."
        )

        notification = (
            BehaviouralNotification.objects
            .select_for_update(skip_locked=True)
            .filter(
                status="PENDING",
                scheduled_at__lte=now
            )
            .order_by("-priority", "scheduled_at")
            .first()
        )

        if not notification:
            return None

        notification.status = "PROCESSING"
        notification.locked_at = now
        notification.attempts += 1

        notification.save(
            update_fields=[
                "status",
                "locked_at",
                "attempts",
                "updated_at"
            ]
        )

        return notification.id


# =====================================================
# SEND NOTIFICATION
# =====================================================

def send_behavioural_notification(notification_id):

    notification = BehaviouralNotification.objects.get(
        id=notification_id
    )

    # Validate before sending.
    valid, reason = validate_notification(notification)

    if not valid:

        notification.status = "CANCELLED"
        notification.cancelled_at = timezone.now()
        notification.error_message = reason
        notification.locked_at = None

        notification.save(
            update_fields=[
                "status",
                "cancelled_at",
                "error_message",
                "locked_at",
                "updated_at"
            ]
        )

        logger.info(
            "Behavioural notification cancelled: %s",
            reason
        )

        return "CANCELLED"

    tokens = DeviceToken.objects.filter(
        phone=notification.customer.phone
    ).values_list("token", flat=True)

    successful = 0
    errors = []

    for token in tokens:

        try:

            send_push_notification(
                token=token,
                title=notification.title,
                body=notification.message,
                high_priority=True,
                data={
                    "type": "behavioural_notification",
                    "trigger": notification.trigger_type,
                    "notification_id": str(notification.id),
                }
            )

            successful += 1

        except Exception as exc:

            errors.append(str(exc))

            logger.exception(
                "Behavioural notification failed for token."
            )

    # At least one device received the notification.
    if successful > 0:

        notification.status = "SENT"
        notification.sent_at = timezone.now()
        notification.error_message = ""

        notification.save(
            update_fields=[
                "status",
                "sent_at",
                "error_message",
                "locked_at",
                "updated_at"
            ]
        )

        logger.info(
            "Behavioural notification %s sent successfully. "
            "Successful devices: %s",
            notification.id,
            successful
        )

        return "SENT"

    # All devices failed.
    error_text = "; ".join(errors)[:4000]

    if notification.attempts < notification.max_attempts:

        notification.status = "PENDING"

        notification.scheduled_at = (
            timezone.now() + timedelta(minutes=5)
        )

    else:

        notification.status = "FAILED"

    notification.error_message = error_text
    notification.locked_at = None

    notification.save(
        update_fields=[
            "status",
            "scheduled_at",
            "error_message",
            "locked_at",
            "updated_at"
        ]
    )

    logger.error(
        "Behavioural notification %s failed. Attempt %s.",
        notification.id,
        notification.attempts
    )

    return notification.status


# =====================================================
# PROCESS NEXT NOTIFICATION
# =====================================================

def process_next_behavioural_notification():

    notification_id = claim_next_notification()

    if not notification_id:
        return None

    try:

        return send_behavioural_notification(
            notification_id
        )

    except Exception as exc:

        logger.exception(
            "Unexpected behavioural notification error: %s",
            notification_id
        )

        try:

            notification = BehaviouralNotification.objects.get(
                id=notification_id
            )

            notification.error_message = str(exc)[:4000]
            notification.locked_at = None

            if notification.attempts >= notification.max_attempts:
                notification.status = "FAILED"
            else:
                notification.status = "PENDING"
                notification.scheduled_at = (
                    timezone.now() + timedelta(minutes=5)
                )

            notification.save()

        except Exception:

            logger.exception(
                "Could not update failed notification."
            )

        return "ERROR"


# =====================================================
# PROCESS BATCH
# =====================================================

def process_behavioural_notification_batch():

    processed = 0

    while processed < BATCH_SIZE:

        result = process_next_behavioural_notification()

        if result is None:
            break

        processed += 1

    return processed