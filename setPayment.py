from datetime import date, datetime
import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

CURRENCY = "lazinne"

debug_this = False

def make_payment(destination, amount, description, transeuro, account_type):

    print("Make Payment to", destination, " for", amount)

    access_token = os.getenv("SPE_ACCESS_KEY")
    spe_url = os.getenv("SPE_URL")
    
    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    url = f"{spe_url}/api/system/payments"
    response = requests.post(
        url,
        headers=headers,
        data=json.dumps({
            "amount": amount,
            "description": description,
            "currency": CURRENCY,
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
    
    headers = {
        "accept": "application/json",
        "Access-Client-Token": access_token,
        "Content-Type": "application/json",
    }

    url = f"{spe_url}/api/users/{user}"
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
        
def get_account_type(account_information):
    print("Get account type")
    
    account_group = account_information.get("group")
    if not account_group:
        raise Exception(f"Missing account group in account information")
    
    account_group_name = account_group.get("internalName")
    if account_group_name == "A3ParticulierStandard":
        account_type = "Emission.CreditParticulierStandard"
    elif account_group_name == "A3ParticulierPremium":
        account_type = "Emission.CreditParticulierPremium"
    else:
        raise Exception(f"Unknown account group")
    
    if debug_this:
        print(f"Account group: {account_group_name}, Account type: {account_type}")
    
    print("Get account type successful")
    return account_type

def main():
    """Main function"""
    try:
        amount = 1.01
        description = "Test payment"
        destination = "jsomville@hotmail.com"
        transeuro = "test-jsb" + datetime.today().strftime("%Y%m%d%H%M%S")
        
        #account_type = "Emission.CreditParticulierPremium"
        
        user_info = get_user_info(destination)
        
        account_type = get_account_type(user_info)

        make_payment(destination, amount, description, transeuro, account_type)

        print("Payment completed successfully")
    except Exception as error:
        print(f"Error in payment: {error}")


if __name__ == "__main__":
    main()
