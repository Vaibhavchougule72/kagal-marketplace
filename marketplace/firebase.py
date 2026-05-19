import firebase_admin

from firebase_admin import credentials
from firebase_admin import messaging

cred = credentials.Certificate(
    "serviceAccountKey.json"
)

firebase_admin.initialize_app(cred)

def send_push_notification(
    token,
    title,
    body
):

    message = messaging.Message(

        notification=messaging.Notification(
            title=title,
            body=body,
        ),

        token=token,
    )

    response = messaging.send(message)

    return response