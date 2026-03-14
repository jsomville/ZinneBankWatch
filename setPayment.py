from datetime import date, datetime
import os
import json
import base64
from urllib.parse import quote
import requests
from dotenv import load_dotenv

load_dotenv()

debug_this = False

def make_payment(destination, amount, description, transeuro, account_type):

    print("Make Payment to", destination, " for", amount)

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
        data=json.dumps({
            "amount": amount,
            "description": description,
            "currency": currency,
            "type": account_type,
            "customValues": {
                "sourceEuro": "virementBancaire",
                "reftranseuro": transeuro,
            },
            "subject": destination,
        }),
    )

    if response.status_code != 201:
        raise Exception(f"Payment failed: {response.status_code} {json.dumps(response.text)}")

    data = response.json()
    print("Payment successful")
    
    if debug_this:
        print("Payment",json.dumps(data, indent=2))

def get_user_info(user):
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
    response = requests.get(
        url,
        headers=headers
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get user info: {response.status_code} {json.dumps(response.text)}")

    data = response.json()
    print("User info retrieved successfully")
    
    if debug_this:
        print("User info",json.dumps(data, indent=2))
        
    return data

def get_user_info_by_account_number(account_number):
    """Search for a user by account number using the search endpoint"""
    print("Retrieve user info by account number", account_number)
    
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
        url,
        headers=headers,
        params={"keywords": account_number}
    )

    if response.status_code != 200:
        raise Exception(f"Failed to search user: {response.status_code} {json.dumps(response.text)}")

    
    data = response.json()
    
    if not data:
        raise Exception(f"No user found for account number {account_number}")
    
    print("test")
    
    # The search returns a list, get the first match
    user = data[0] if isinstance(data, list) else data
    
    if debug_this:
        print("User found:", json.dumps(user, indent=2))
    
    # Now get the full user details
    user_id = user.get("id")
    if user_id:
        return get_user_info(user_id)
    
    return user
        
def get_account_type(account_information):
    print("Get account type")
    
    account_group = account_information.get("group")
    if not account_group:
        raise Exception(f"Missing account group in account information")
    
    account_group_name = account_group.get("internalName")
    if account_group_name == "A2ParticulierGuest":
        account_type = "Emission.CreditParticulierGuest"
    elif account_group_name == "A3ParticulierGuest":
        account_type = "Emission.CreditParticulierGuest"
    elif account_group_name == "A2ParticulierStandard":
        account_type = "Emission.CreditParticulierStandard"
    elif account_group_name == "A3ParticulierStandard":
        account_type = "Emission.CreditParticulierStandard"
    elif account_group_name == "A2ParticulierPremium":
        account_type = "Emission.CreditParticulierPremium"
    elif account_group_name == "A3ParticulierPremium":
        account_type = "Emission.CreditParticulierPremium"
    else:
        print(f"Unknown account group: {account_group_name}")
        raise Exception(f"Unknown account group")
    
    if debug_this:
        print(f"Account group: {account_group_name}, Account type: {account_type}")
    
    print("Get account type successful")
    return account_type

def search_user():
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
        url,
        headers=headers,
        params={"pageSize": 2000}
    )

    if response.status_code != 200:
        raise Exception(f"Failed to search user: {response.status_code} {json.dumps(response.text)}")

    data = response.json()
    return data

def update_user_list():
    #S-step 1 get the users
    data = search_user()
    print(f"Users retrieved successfully {len(data)} users found")
   
    #Step 2 -- call the /account to get the account number
    user_list = []
    for user in data:
        try:
            user_id = user.get("id")
            account_number= ""
            email = ""
            account_type = ""
             
            #print(f"User {user_id} has {json.dumps(user, indent=2)}")
            
            detail_user = get_user_info(user_id)
            if detail_user:
                #print(f"User detail for {user_id} has {json.dumps(detail_user, indent=2)}")
                email = detail_user.get("email")
                
                permissions = detail_user.get("permissions")
                #print(f"Accounts {json.dumps(permissions, indent=2)}")
                if permissions:
                    accounts = permissions.get("accounts")
                    #print(f"Accounts {json.dumps(accounts, indent=2)}")
                    if accounts:
                        account = accounts[0] if accounts else None
                        account_number = account.get("number") if account else None
                
                #account_type = detail_user.get("group") if detail_user else None
                account_type = get_account_type(detail_user) if detail_user else None
            
            user_detail = {
                "id": user_id,
                "display": user["display"],
                "email": email,
                "account_number": account_number,
                "account_type" : account_type
            }
            
            print(f"User {user_id} has {json.dumps(user_detail, indent=2)}")
            
            user_list.append(user_detail)
            
        except Exception as error:
            print(f"Error getting account info for user {user_id}: {error}")
    
    #Save file to disk
    with open("user_list.json", "w") as f:
        json.dump(user_list, f, indent=2)

def get_user_info_from_account(account):

    #Open file
    with open("user_list.json", "r") as f:
        user_list = json.load(f)
        #Search for the account number
        for user in user_list:
            if user["account_number"] == account:
                return user
    return None


def transaction_test():
    """Main function"""
    try:
        amount = 1.01
        account_number="114-8844-79676"
        
        #************
        
        user_info = get_user_info_from_account(account_number)
        if not user_info:
            raise Exception(f"No user found for account number {account_number}")
        
        destination = user_info["email"]
        account_type = user_info["account_type"]
        
        #Use this now so we have a unique transeuro for each payment, otherwise we get an error about duplicate transeuro
        transeuro = "Test-" + datetime.today().strftime("%Y%m%d%H%M%S")
        
        #The recommended transeuro format is 2026-03-02/114-1034-78116/150,00
        transeuro = f"{datetime.today().strftime('%Y-%m-%d')}/{account_number}/{amount:.2f}"
        
        description = transeuro

        make_payment(destination, amount, description, transeuro, account_type)

        print("Payment completed successfully")
    except Exception as error:
        print(f"Error in payment: {error}")

if __name__ == "__main__":
    #update_user_list()
    transaction_test()
