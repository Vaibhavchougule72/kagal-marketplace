import requests
import os

def send_sms(phone, message):

    api_key = os.getenv("SMS_API_KEY")

    if not api_key:
        print("❌SMS_API_KEY missing")
        return None

    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "sender_id":"TXTIND",
        "message": message,
        "language": "english",
        "route": "v",
        "numbers": phone
    }

    headers = {
        "authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print("SMS RESPONSE:", response.json())
        return response.json()

    except Exception as e:
        print("SMS Error:", e)
        return None