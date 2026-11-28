import logging

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from marketplace.models import (
    CustomerActivity,
    BehaviouralActivityProcessing,
)

from marketplace.behavioural_notifications.service import (
    schedule_behavioural_notification,
    cancel_pending_notifications,
)

logger = logging.getLogger(__name__)


# =====================================================
# SCHEDULER SETTINGS
# =====================================================

BATCH_SIZE = 100

ACTIVITY_LOOKBACK_MINUTES = 30

MAX_PROCESSING_ATTEMPTS = 3

STALE_PROCESSING_MINUTES = 10


SUPPORTED_EVENTS = [
    "VISIT",
    "EXPLORE",
    "PRODUCT_VIEW",
    "ADD_TO_CART",
    "CHECKOUT",
    "ORDER_PLACED",
]


# =====================================================
# RECOVER INTERRUPTED ACTIVITIES
# =====================================================

def recover_stale_activities():

    cutoff = timezone.now() - timedelta(
        minutes=STALE_PROCESSING_MINUTES
    )

    updated = BehaviouralActivityProcessing.objects.filter(
        status="PROCESSING",
        updated_at__lt=cutoff,
    ).update(
        status="FAILED",
        error_message="Recovered after scheduler interruption."
    )

    if updated:
        logger.warning(
            "Recovered %s interrupted activity records.",
            updated
        )


# =====================================================
# PROCESS ONE ACTIVITY
# =====================================================

def process_activity(activity):

    event_type = activity.event_type

    # -------------------------------------------------
    # ORDER PLACED: CANCEL PENDING REMINDERS
    # -------------------------------------------------

    if event_type == "ORDER_PLACED":

        cancel_pending_notifications(
            activity.session,
            reason="Customer placed an order."
        )

        return "PROCESSED"

    # -------------------------------------------------
    # OTHER BEHAVIOURAL EVENTS
    # -------------------------------------------------

    notification = schedule_behavioural_notification(
        activity
    )

    if notification:
        return "PROCESSED"

    # No notification needed, e.g. anonymous visitor
    # or customer without a registered device.
    return "IGNORED"


# =====================================================
# PROCESS ACTIVITY WITH DUPLICATE PROTECTION
# =====================================================

def process_activity_safely(activity_id):

    with transaction.atomic():

        activity = (
            CustomerActivity.objects
            .select_related("session", "session__customer")
            .select_for_update(of=("self",))
            .get(id=activity_id)
        )

        record, created = (
            BehaviouralActivityProcessing.objects
            .select_for_update()
            .get_or_create(
                activity=activity,
                defaults={
                    "status": "PROCESSING",
                    "attempts": 0,
                }
            )
        )

        if not created:

            if record.status in ("PROCESSED", "IGNORED"):
                return record.status

            if record.status == "PROCESSING":
                return "SKIPPED"

            if record.attempts >= MAX_PROCESSING_ATTEMPTS:
                return "FAILED"

            record.status = "PROCESSING"
            record.error_message = ""
            record.save(
                update_fields=[
                    "status",
                    "error_message",
                    "updated_at"
                ]
            )

        record.attempts += 1

        record.save(
            update_fields=[
                "attempts",
                "updated_at"
            ]
        )

    # Process outside the locking transaction.
    try:

        result = process_activity(activity)

        record.status = result
        record.processed_at = timezone.now()
        record.error_message = ""

        record.save(
            update_fields=[
                "status",
                "processed_at",
                "error_message",
                "updated_at"
            ]
        )

        return result

    except Exception as exc:

        logger.exception(
            "Failed to process customer activity %s",
            activity_id
        )

        record.status = "FAILED"
        record.error_message = str(exc)[:4000]

        record.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at"
            ]
        )

        return "FAILED"


# =====================================================
# DISCOVER NEW ACTIVITIES
# =====================================================

def discover_and_schedule_behavioural_notifications():

    recover_stale_activities()

    now = timezone.now()

    lookback = now - timedelta(
        minutes=ACTIVITY_LOOKBACK_MINUTES
    )

    activities = (
        CustomerActivity.objects
        .filter(
            event_type__in=SUPPORTED_EVENTS,
            created_at__gte=lookback,
        )
        .filter(
            Q(processing_record__isnull=True)
            |
            Q(
                processing_record__status="FAILED",
                processing_record__attempts__lt=MAX_PROCESSING_ATTEMPTS
            )
        )
        .select_related(
            "session",
            "session__customer"
        )
        .order_by("created_at", "id")[:BATCH_SIZE]
    )

    processed = 0
    ignored = 0
    failed = 0

    for activity in activities:

        result = process_activity_safely(activity.id)

        if result == "PROCESSED":
            processed += 1

        elif result == "IGNORED":
            ignored += 1

        elif result == "FAILED":
            failed += 1

    if processed or ignored or failed:

        logger.info(
            "Behavioural scheduler summary: "
            "Processed=%s, Ignored=%s, Failed=%s",
            processed,
            ignored,
            failed
        )

    return {
        "processed": processed,
        "ignored": ignored,
        "failed": failed,
    }