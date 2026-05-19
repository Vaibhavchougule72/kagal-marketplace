import os
import json
import firebase_admin

from firebase_admin import credentials
from firebase_admin import messaging

firebase_json = os.environ.get(
    "FIREBASE_CREDENTIALS"
)

cred_dict = json.loads(firebase_json)

cred = credentials.Certificate(
    cred_dict
)

if not firebase_admin._apps:

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