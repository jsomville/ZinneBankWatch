from datetime import date, datetime
import os
import json
import traceback
from urllib.parse import quote
import requests
import uuid
from dotenv import load_dotenv
from logger import log_this, config_logging

load_dotenv()

user_file_path = "user_list.json"
debug_this = False

global_user_list = []


def make_payment(destination, amount, description, transeuro, account_type):
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


def get_user_info(user):
    """Get user information by user id"""
    if debug_this:
        print("Retrieve user info for", user)

    access_token = os.getenv("SPE_ACCESS_KEY")
    spe_url = os.getenv("SPE_URL")
    currency = os.getenv("CURRENCY")

    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    # URL-encode the user identifier to handle special characters like dashes
    url = f"{spe_url}{currency}/api/users/{user}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"Failed to get user info: {response.status_code} {json.dumps(response.text)}"
        )

    data = response.json()

    if debug_this:
        print("User info", json.dumps(data, indent=2))

    return data


def get_account_type(account_information):
    """Get the account type based on the internalName of the group the user is in"""
    if debug_this:
        print(
            "Get account type for user with account information",
            json.dumps(account_information, indent=2),
        )

    account_group = account_information.get("group")
    if not account_group:
        raise Exception(f"Missing account group in account information")

    # By default Standard group
    account_type = "Emission.CreditParticulierStandard"

    # Check if premium
    account_group_name = account_group.get("internalName")
    if "Premium" in account_group_name:
        account_type = "Emission.CreditParticulierPremium"

    if debug_this:
        print(f"Account group is : {account_type}")

    return account_type


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


def get_user_details(user):

    user_id = user.get("id")
    account_number = ""
    email = ""
    account_type = ""

    detail_user = get_user_info(user_id)
    if detail_user:
        email = detail_user.get("email")

        permissions = detail_user.get("permissions")
        if permissions:
            accounts = permissions.get("accounts")
            if accounts:
                account = accounts[0] if accounts else None
                account_number = account.get("number") if account else None

        account_type = get_account_type(detail_user) if detail_user else None

    user_detail = {
        "id": user_id,
        "display": user["display"],
        "email": email,
        "account_number": account_number,
        "account_type": account_type,
    }

    if debug_this:
        print(f"User {user_id} has {json.dumps(user_detail, indent=2)}")

    return user_detail

def create_user_list():

    # Step 1 get all the users
    data = get_all_users()

    if debug_this:
        print(f"Users retrieved successfully {len(data)} users found")

    # Step 2 -- call the /account to get the account assigend to that user
    user_list = []
    for user in data:
        try:
            
            user_detail = get_user_details(user)

            user_list.append(user_detail)

        except Exception as error:
            message = json.dumps({
                "error": str(error),
                "traceback": traceback.format_exc().splitlines()
            }, indent=2)
            log_this("error", f"Error getting account info for user {user.get('id')}: {message}")

    # Save file to disk
    save_user_list(user_list)

def save_user_list(user_list):
    try:
        with open(user_file_path, "w") as f:
            json.dump(user_list, f, indent=2, ensure_ascii=False)
    except Exception as error:       
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error saving user list to file: {message}")
        raise

def get_user_info_from_account(account):
    global global_user_list

    if len(global_user_list) == 0:
        log_this("info", "Loading user list from file")

        # Checks if file exists, if not update the user list and save file
        if not os.path.exists(user_file_path):
            log_this("info", "File not found, creating user file this will take some time")
            create_user_list()

        # Open file & Load File
        with open(user_file_path, "r") as f:
            global_user_list = json.load(f)

    # Search for the account number
    for user in global_user_list:
        if user["account_number"] == account:
            return user

    #User not found check if need to update the list
    data = get_all_users()
    if len(data) != len(global_user_list):
        log_this("info", "Updating user list")
        
        # Search for the account number again
        user_added = False
        for user in data:
            #Is the user in the global list
            user_in_global_list = get_user_info_from_email(user["email"])
            if not user_in_global_list:
                log_this("info", f"New user found {user['email']}, updating user list")
                
                user_detail = get_user_details(user)
                global_user_list.append(user_detail)
                user_added = True

                if user_detail["account_number"] == account:
                    return user_detail
                
        if user_added:
            save_user_list(global_user_list)
    
    return None

def get_user_info_from_email(email):
    global global_user_list
    
    for user in global_user_list:
        if user["email"] == email:
            return user

    return None

def process_payment(production_flag, unique_number, amount, account_number, transaction_dateTime):
    try:

        log_this("info", f"Processing payment {unique_number} for account {account_number} with amount {amount}")

        user_info = get_user_info_from_account(account_number)
        if not user_info:
            raise Exception(f"No user found for account number {account_number}")

        destination = user_info["email"]
        account_type = user_info["account_type"]

        # Current Transeuro format takes only date --> bugs if 2 deposit of same amount on same day
        transeuro = (
            f"{transaction_dateTime.strftime('%Y-%m-%d')}/{account_number}/{amount:.2f}"
        )
        if not production_flag:
            prefix = str(unique_number)[
                :8
            ]  # Use the first 8 characters of the UUID for uniqueness
            transeuro = f"Test - {prefix} - {transaction_dateTime.strftime('%Y-%m-%d')}/{account_number}/{amount:.2f}"

        description = transeuro
        
        log_this("info", f"Processing payment {unique_number} transeuro {transeuro}")

        make_payment(destination, amount, description, transeuro, account_type)

        log_this("info", "Payment completed successfully")

    except Exception as error:    
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error processing payment: {message}")
        raise

def get_unprocessed_reason(string):
    reason = "unknown"
    if "reftranseuro" in string and "transaction euro must be unique" in string:
        reason = "Ref Trans Euro must be unique"
    elif "No user found for account number" in string:
        reason = string
    return reason

def test_transaction():
    try:
        log_this("info", "Begin Testing transactions processing")

        amount = 1.01
        account_number = "114-8844-79676"
        unique_id = uuid.uuid4()
        process_payment(False, unique_id, amount, account_number, datetime.now())

        # ************
        amount = 0.99
        account_number = "114-8844-79676"
        unique_id = uuid.uuid4()
        process_payment(False, unique_id, amount, account_number, datetime.now())

        # ************
        amount = 0.1
        account_number = "114-8844-79676"
        unique_id = uuid.uuid4()
        process_payment(False, unique_id, amount, account_number, datetime.now())

        # ************
        amount = 100
        account_number = "114-8844-79676"
        unique_id = uuid.uuid4()
        process_payment(False, unique_id, amount, account_number, datetime.now())

        log_this("info", "Testing transactions completed")
    except Exception as error:
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error in payment: {message}")

if __name__ == "__main__":

    config_logging()

    test_transaction()

    # user = get_user_info("543310456861094502")
    # print(f"Users retrieved successfully {json.dumps(user, indent=2)}")

    # data = get_all_users()

    # print(f"Users retrieved successfully {len(data)} users found")

    # last_user = data[-1:]
    # print(f" last user {json.dumps(last_user, indent=2, ensure_ascii=False)}")

# create_user_list()
