import json
import os
from dotenv import load_dotenv
import requests

load_dotenv()

API_URL = os.getenv("SIGNAL_URL")
SENDER_NUMBER = os.getenv("SIGNAL_SOURCE_NUMBER")

def send_signal_message(recipients, message, timeout=10):
    """Send a message using the Signal REST API."""

    url = f"{API_URL.rstrip('/')}/v2/send"
    headers = {"Content-Type": "application/json"}
    payload = {
        "message": message,
        "number": SENDER_NUMBER,
        "recipients": recipients,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()

    if response.text:
        return response.json()
    return {"status": "ok", "status_code": response.status_code}

def list_group(timeout=10):
    """List groups using the Signal REST API."""
    """Use this to identify the group ID for the destination group."""

    url = f"{API_URL.rstrip('/')}/v1/groups/{SENDER_NUMBER}"
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    if response.text:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return {"status": "ok", "status_code": response.status_code}


if __name__ == "__main__":
   
    #*********************************
    destination_group = os.getenv("SIGNAL_DESTINATION_GROUP")
    recipients = []
    recipients.append(destination_group)
    
    message = "Test message via signal-cli!"
    #*********************************
    
    print(f"Sending message from {SENDER_NUMBER} to {recipients} via Signal API...")
    
    result = send_signal_message(
        recipients=recipients,
        message=message,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    ##list_group()
    
