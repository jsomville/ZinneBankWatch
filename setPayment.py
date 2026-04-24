from datetime import datetime
import os
import json
import traceback
import uuid
from dotenv import load_dotenv
from logger import log_this, config_logging

from spe import make_payment, get_user_info, get_all_users

load_dotenv()

DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)
    
USER_FILE = os.path.join(DATA_FOLDER, "user_list.json")

global_user_list = []

debug_this = False

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

def map_user_details(user_info):
    """Get the user details including email, account number and account type"""
    account_number = ""
    account_type = ""

    permissions = user_info.get("permissions")
    if permissions:
        accounts = permissions.get("accounts")
        if accounts:
            account = accounts[0] if accounts else None
            account_number = account.get("number") if account else None

    account_type = get_account_type(user_info) if user_info else None

    user_detail = {
        "id": user_info.get("id"),
        "display": user_info.get("display"),
        "email": user_info.get("email"),
        "account_number": account_number,
        "account_type": account_type,
    }

    if debug_this:
        print(f"User {user_info.get('id')} has {json.dumps(user_detail, indent=2)}")

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
            
            user_info = get_user_info(user.get("id"))
            
            user_detail = map_user_details(user_info)

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
        with open(USER_FILE, "w") as f:
            json.dump(user_list, f, indent=2, ensure_ascii=False)
    except Exception as error:       
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error saving user list to file: {message}")
        raise

def find_user_info_from_account(account_number: str):
    global global_user_list

    #Check if local list is empty, if yes load from file
    if len(global_user_list) == 0:
        log_this("info", "Loading user list from file")

        # Checks if file exists, if not update the user list and save file
        if not os.path.exists(USER_FILE):
            log_this("info", "File not found, creating user file this will take some time")
            create_user_list()

        # Open file & Load File
        with open(USER_FILE, "r") as f:
            global_user_list = json.load(f)

    # Search for the account number
    for user in global_user_list:
        if user["account_number"] == account_number:
            #If account match return user info
            return user

    #User not found check if need to update the list
    data = get_all_users()
    print(f"Number of users in global list {len(global_user_list)}, number of users retrieved from API {len(data)}")
        
    new_user = None
    if len(data) != len(global_user_list):
        log_this("info", "Updating user list")
        
        # Search for the account number again
        user_added = 0
        for user in data:
            #Is the user in the global list
            user_id = user.get("id")
            user_in_global_list = find_user_info_from_id(user_id)
            if not user_in_global_list:
                log_this("info", f"New user found {user_id}")
                
                user_info = get_user_info(user_id)
                
                user_detail = map_user_details(user_info)
                
                global_user_list.append(user_detail)
                user_added += 1

                if user_detail["account_number"] == account_number:
                    new_user = user_detail
                
        if user_added > 0:
            log_this("info", f"{user_added} new users added to the list, saving file")
            save_user_list(global_user_list)
    
    return new_user

def find_user_info_from_email(email: str):
    global global_user_list
    
    for user in global_user_list:
        if user["email"] == email:
            return user

    return None

def find_user_info_from_id(user_id: str):
    global global_user_list
    
    for user in global_user_list:
        if user["id"] == user_id:
            return user

    return None

def process_payment(production_flag: bool, unique_number: str, amount: float, account_number: str, transaction_dateTime: datetime):
    try:

        log_this("info", f"Processing payment {unique_number} for account {account_number} with amount {amount}")

        user_info = find_user_info_from_account(account_number)
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
        
        return transeuro

    except Exception as error:    
        message = json.dumps({
            "error": str(error),
            "traceback": traceback.format_exc().splitlines()
        }, indent=2)
        log_this("error", f"Error processing payment: {message}")
        raise

def get_unprocessed_reason(reason_string: str):
    reason = "unknown"
    if "reftranseuro" in reason_string and "transaction euro must be unique" in reason_string:
        reason = "RefTransEuro must be unique"
    elif "No user found for account number" in reason_string:
        reason = "No User found"
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
        
def test_user_list():
    
    account_number="999-9511-35955" #This should be a newly created user...

    user = find_user_info_from_account(account_number)
    
    print(f"User info for account {account_number} is {json.dumps(user, indent=2)}")
            

if __name__ == "__main__":

    config_logging()

    test_user_list()


    #create_user_list()
