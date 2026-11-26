import logging

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from marketplace.models import (
    Customer,
    CustomerActivity,
    DeviceToken,
    BehaviouralNotification,
)

logger = logging.getLogger(__name__)


# =====================================================
# BEHAVIOURAL NOTIFICATION RULES
# =====================================================

NOTIFICATION_RULES = {

    "VISIT": {
        "delay": 15,
        "priority": 1,
        "title": "Hungry? LOKA is here! 🍔",
        "message": "Your favourite food is just a few taps away. Explore LOKA and order now!",
    },

    "EXPLORE": {
        "delay": 15,
        "priority": 2,
        "title": "Found something delicious? 😋",
        "message": "Your favourite local food is waiting for you on LOKA. Place your order today!",
    },

    "PRODUCT_VIEW": {
        "delay": 15,
        "priority": 3,
        "title": "Still thinking about it? 🍕",
        "message": "That delicious food you checked out is waiting for you. Order it on LOKA!",
    },

    "ADD_TO_CART": {
        "delay": 10,
        "priority": 4,
        "title": "Your food is waiting! 🛒",
        "message": "You added something delicious to your cart. Complete your order on LOKA!",
    },

    "CHECKOUT": {
        "delay": 10,
        "priority": 5,
        "title": "Almost there! ❤️",
        "message": "Your order is just one step away. Complete your checkout on LOKA!",
    },

}


# Maximum behavioural notifications per customer
# within the previous 24 hours.

MAX_NOTIFICATIONS_PER_DAY = 2


# =====================================================
# CUSTOMER RESOLUTION
# =====================================================

def get_notification_customer(activity):

    session = activity.session

    customer = session.customer

    if not customer and session.phone:

        customer = Customer.objects.filter(
            phone=session.phone,
            is_active=True
        ).first()

    if not customer:
        return None

    # Require at least one registered device token.
    has_device = DeviceToken.objects.filter(
        phone=customer.phone
    ).exists()

    if not has_device:
        return None

    return customer


# =====================================================
# CANCEL PENDING NOTIFICATIONS
# =====================================================

def cancel_pending_notifications(session, reason=""):

    now = timezone.now()

    updated = BehaviouralNotification.objects.filter(
        session=session,
        status="PENDING"
    ).update(
        status="CANCELLED",
        cancelled_at=now,
        error_message=reason
    )

    if updated:
        logger.info(
            "Cancelled %s behavioural notifications for session %s",
            updated,
            session.id
        )

    return updated


# =====================================================
# SCHEDULE NOTIFICATION
# =====================================================

@transaction.atomic
def schedule_behavioural_notification(activity):

    event_type = activity.event_type

    # Ignore unsupported events.
    if event_type not in NOTIFICATION_RULES:
        return None

    session = activity.session

    # Ignore events belonging to an order-completed session.
    if session.activities.filter(
        event_type="ORDER_PLACED"
    ).exists():

        logger.info(
            "Notification skipped: order already placed in session %s",
            session.id
        )

        return None

    customer = get_notification_customer(activity)

    if not customer:
        logger.info(
            "Notification skipped: no registered customer/device. "
            "Session: %s",
            session.id
        )
        return None

    rule = NOTIFICATION_RULES[event_type]

    priority = rule["priority"]

    # -------------------------------------------------
    # FREQUENCY CAP
    # -------------------------------------------------

    since = timezone.now() - timedelta(days=1)

    sent_count = BehaviouralNotification.objects.filter(
        customer=customer,
        status="SENT",
        sent_at__gte=since
    ).count()

    if sent_count >= MAX_NOTIFICATIONS_PER_DAY:

        logger.info(
            "Daily behavioural notification limit reached "
            "for customer %s",
            customer.phone
        )

        return None

    # -------------------------------------------------
    # CHECK EXISTING SESSION NOTIFICATIONS
    # -------------------------------------------------

    existing = BehaviouralNotification.objects.filter(
        session=session
    )

    # If a notification was already sent in this session,
    # don't send another behavioural reminder.
    if existing.filter(status="SENT").exists():

        logger.info(
            "Notification skipped: session already received "
            "a behavioural notification. Session: %s",
            session.id
        )

        return None

    # A higher-priority pending notification already exists.
    higher_priority_exists = existing.filter(
        status="PENDING",
        priority__gt=priority
    ).exists()

    if higher_priority_exists:

        logger.info(
            "Lower-priority notification skipped. "
            "Session: %s, event: %s",
            session.id,
            event_type
        )

        return None

    # Cancel lower-priority pending notifications.
    existing.filter(
        status="PENDING",
        priority__lt=priority
    ).update(
        status="CANCELLED",
        cancelled_at=timezone.now(),
        error_message="Superseded by a higher-priority activity."
    )

    # If the same or higher priority notification is already pending,
    # don't create another notification.
    same_or_higher_exists = existing.filter(
        status="PENDING",
        priority__gte=priority
    ).exists()

    if same_or_higher_exists:
        return None

    # -------------------------------------------------
    # CREATE NOTIFICATION
    # -------------------------------------------------

    scheduled_at = (
        activity.created_at
        + timedelta(minutes=rule["delay"])
    )

    notification = BehaviouralNotification.objects.create(

        customer=customer,

        session=session,

        activity=activity,

        trigger_type=event_type,

        title=rule["title"],

        message=rule["message"],

        priority=priority,

        scheduled_at=scheduled_at,

        status="PENDING",

    )

    logger.info(
        "Behavioural notification scheduled. "
        "Customer: %s, Event: %s, Scheduled: %s",
        customer.phone,
        event_type,
        scheduled_at
    )

    return notification