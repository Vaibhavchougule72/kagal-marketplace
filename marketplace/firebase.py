import json
import logging
import os

import firebase_admin
from firebase_admin import credentials, messaging
import time
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

logger = logging.getLogger(__name__)


# =====================================================
# FIREBASE INITIALIZATION
# =====================================================

firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_FILE")
firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_credentials_path:
    with open(firebase_credentials_path, "r", encoding="utf-8") as f:
        firebase_json = f.read()

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully.")

    except Exception as e:
        logger.exception("Firebase initialization failed: %s", e)

else:
    logger.warning("FIREBASE_CREDENTIALS environment variable not found.")


# =====================================================
# COMMON HELPERS
# =====================================================

def _android_config(high_priority=False):
    """
    Common Android configuration used by all notifications.
    """

    priority = "high" if high_priority else "normal"

    return messaging.AndroidConfig(
        priority=priority,
        notification=messaging.AndroidNotification(
            channel_id="LOKA_ORDER_UPDATES_V2",
            sound="default",
            priority=priority,
        ),
    )


def _chunk_list(items, size=500):
    """
    Firebase allows max 500 tokens per multicast request.
    """

    for i in range(0, len(items), size):
        yield items[i:i + size]


# =====================================================
# SINGLE PUSH NOTIFICATION
# =====================================================

def send_push_notification(
    token,
    title,
    body,
    high_priority=True,
    data=None,
):
    """
    Send notification to a single device.
    """

    if not token:
        raise ValueError("FCM token is empty")

    message = messaging.Message(
        notification=messaging.Notification(
            title=str(title),
            body=str(body),
        ),

        data={
            "title": str(title),
            "body": str(body),
            **(data or {}),
        },

        android=_android_config(high_priority),

        token=token,
    )

    try:

        response = messaging.send(message)

        logger.info(
            "Push notification sent: %s",
            response,
        )

        return response

    except Exception as e:

        logger.exception(
            "Push notification failed: %s",
            e,
        )

        raise


# =====================================================
# BULK PUSH NOTIFICATIONS
# =====================================================

# =====================================================
# BULK PUSH NOTIFICATIONS
# =====================================================

def send_bulk_push_notifications(
    tokens,
    title,
    body,
    high_priority=False,
    data=None,
):
    """
    Send notifications to multiple devices.

    Returns:
    {
        "success": int,
        "failed": int,
        "invalid_tokens": []
    }
    """

    tokens = list(dict.fromkeys(
        token for token in tokens if token
    ))

    if not tokens:
        return {
            "success": 0,
            "failed": 0,
            "invalid_tokens": [],
        }

    if not firebase_admin._apps:
        raise RuntimeError(
            "Firebase is not initialized. "
            "Check the FIREBASE_CREDENTIALS environment variable."
        )

    success = 0
    failed = 0
    invalid_tokens = []

    notification = messaging.Notification(
        title=str(title),
        body=str(body),
    )

    android = _android_config(high_priority)

    message_data = {
        "title": str(title),
        "body": str(body),
    }

    if data:
        message_data.update({
            str(key): str(value)
            for key, value in data.items()
        })

    for batch_number, batch in enumerate(
        _chunk_list(tokens, 500),
        start=1,
    ):

        multicast = messaging.MulticastMessage(
            tokens=batch,
            notification=notification,
            android=android,
            data=message_data,
        )

        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                response = messaging.send_each_for_multicast(
                    multicast
                )

                success += response.success_count
                failed += response.failure_count

                logger.info(
                    "FCM batch %s completed. "
                    "Total tokens: %s, successful: %s, failed: %s",
                    batch_number,
                    len(batch),
                    response.success_count,
                    response.failure_count,
                )

                for token, result in zip(batch, response.responses):
                    if result.success:
                        continue

                    exception = result.exception

                    logger.warning(
                        "FCM delivery failed for token "
                        "(batch=%s): %s",
                        batch_number,
                        exception,
                    )

                    if isinstance(
                        exception,
                        messaging.UnregisteredError,
                    ):
                        invalid_tokens.append(token)

                break

            except Exception as exc:
                logger.exception(
                    "FCM batch %s failed on attempt %s/%s",
                    batch_number,
                    attempt,
                    max_attempts,
                )

                if attempt < max_attempts:
                    time.sleep(2 ** attempt)
                else:
                    failed += len(batch)

    result = {
        "success": success,
        "failed": failed,
        "invalid_tokens": invalid_tokens,
    }

    logger.info(
        "FCM campaign sending finished: %s",
        result,
    )

    return result


# ============================================================
# PARTNER NEW ORDER NOTIFICATION
# ============================================================

def send_partner_new_order_notification(token, order):

    message = messaging.Message(

        data={
            "type": "NEW_ORDER",

            "order_id": str(order.id),

            "store_id": str(order.store_id),

            "customer_name": str(
                order.customer_name
            ),

            "payment_method": str(
                order.payment_method
            ),

            "total": str(
                order.total
            ),

            "subtotal": str(order.subtotal),

            "created_at": order.created_at.isoformat(),
        },

        token=token,

        android=messaging.AndroidConfig(
            priority="high"
        )
    )

    return messaging.send(message)

def send_partner_order_alert_cancelled(token, order):
    message = messaging.Message(
        data={
            "type": "CANCEL_ORDER_ALERT",
            "order_id": str(order.id),
        },
        token=token,
        android=messaging.AndroidConfig(
            priority="high"
        )
    )

    return messaging.send(message)


def notify_partner_order_alert_cancelled(order):
    if not order:
        return

    from .models import PartnerDeviceToken

    tokens = (
        PartnerDeviceToken.objects
        .filter(
            store=order.store,
            is_active=True
        )
        .values_list("token", flat=True)
    )

    for token in tokens:
        try:
            send_partner_order_alert_cancelled(
                token,
                order
            )

        except Exception as e:
            print(
                "❌ Partner cancel alert FCM Error:",
                str(e)
            )