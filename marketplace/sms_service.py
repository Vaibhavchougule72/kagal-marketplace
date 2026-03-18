import requests
import os

def send_sms(phone, message):

    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "message": message,
        "language": "english",
        "route": "v",
        "numbers": phone
    }

    headers = {
        "authorization": os.getenv("FAST2SMS_API_KEY"),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print("SMS RESPONSE:", response.json())   # 🔥 IMPORTANT DEBUG
        return response.json()

    except Exception as e:
        print("SMS Error:", e)
        return None