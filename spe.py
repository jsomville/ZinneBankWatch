import os
import json
import requests

from dotenv import load_dotenv

load_dotenv()

debug_this = False

def make_payment(destination: str, amount: float, description: str, transeuro: str, account_type: str):
    """Make a payment to the destination email with the specified amount and description"""

    if debug_this:
        print(f" Make Payment to {destination} for {amount}")

    access_token = os.getenv("SPE_ACCESS_KEY")
    spe_url = os.getenv("SPE_URL")
    currency = os.getenv("CURRENCY")

    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    url = f"{spe_url}{currency}/api/system/payments"

    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(
            {
                "amount": amount,
                "description": description,
                "currency": currency,
                "type": account_type,
                "customValues": {
                    "sourceEuro": "virementBancaire",
                    "reftranseuro": transeuro,
                },
                "subject": destination,
            }
        ),
    )

    if response.status_code != 201:
        raise Exception(
            f"Payment failed: {response.status_code} {json.dumps(response.text)}"
        )

    data = response.json()

    if debug_this:
        print("Payment", json.dumps(data, indent=2))


def get_user_info(user_id: str):
    """Get user information by user id"""
    if debug_this:
        print("Retrieve user info for", user_id)

    access_token = os.getenv("SPE_ACCESS_KEY")
    spe_url = os.getenv("SPE_URL")
    currency = os.getenv("CURRENCY")

    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    # URL-encode the user identifier to handle special characters like dashes
    url = f"{spe_url}{currency}/api/users/{user_id}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"Failed to get user info: {response.status_code} {json.dumps(response.text)}"
        )

    data = response.json()

    if debug_this:
        print("User info", json.dumps(data, indent=2))

    return data

def get_all_users():

    access_token = os.getenv("SPE_ACCESS_KEY")
    spe_url = os.getenv("SPE_URL")
    currency = os.getenv("CURRENCY")

    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    url = f"{spe_url}{currency}/api/users"
    response = requests.get(
        url, headers=headers, params={"groups": "AParticuliers", "pageSize": 2000}
    )

    if response.status_code != 200:
        raise Exception(
            f"Failed to search user: {response.status_code} {json.dumps(response.text)}"
        )

    data = response.json()

    if debug_this:
        print(
            f"Users retrieved successfully {json.dumps(data, indent=2, ensure_ascii=False )}"
        )

    return data


def test_get_info():
    user_id = 543310456861094502
    print(f"**************************************")
    print(f"     Get One User {user_id}")
    print(f"**************************************")
    #Get one user info by id
    user = get_user_info(str(user_id))
    display_name = user.get("display")
    print(f"User display name: {display_name}")
    email = user.get("email")
    print(f"User email: {email}")
    
    print(f"**************************************")
    print(f"     Get User list")
    print(f"**************************************")
    data = get_all_users()
    print(f"Users retrieved successfully {len(data)} users found")
    last_user = data[-1:]
    print(f" last user {json.dumps(last_user, indent=2, ensure_ascii=False)}")
    

if __name__ == "__main__":

    test_get_info()
