import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_access_token():
    """Authenticate with the MyPonto OAuth2 API"""
    print("Logging in...")
    try:
        client_id = os.getenv("MY_PONTO_ID")
        client_secret = os.getenv("MY_PONTO_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Missing MY_PONTO_ID or MY_PONTO_SECRET in environment variables")
        
        # Create Basic Auth header
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        response = requests.post(
            "https://api.myponto.com/oauth2/token",
            headers=headers,
            data={"grant_type": "client_credentials"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.status_code} {response.text}")
        
        data = response.json()
        print("Login successful")
        print(f"Access Token: {data.get('access_token')}")
        return data
    except Exception as error:
        print(f"Login error: {error}")
        raise
    
    

def get_bank_account_details(access_token):
    """Get bank account details"""
    print("Getting bank account details...")
    try:
       
        if not access_token:
            raise ValueError("Missing access token")
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.get('access_token')}"
        }
        
        response = requests.get(
            "https://api.myponto.com/accounts",
            headers=headers,
            data={"grant_type": "client_credentials"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.status_code} {response.text}")
        
        data = response.json()
        print("Get Bank Account Details successful")
        print(json.dumps(data, indent=2))
        return data
    except Exception as error:
        print(f"Error getting bank account details: {error}")
        raise
    
def get_account_transactions(access_token, account_id):
    """Get transactions for a specific bank account"""
    print(f"Getting transactions for account {account_id}...")
    try:
        if not access_token:
            raise ValueError("Missing access token")
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.get('access_token')}"
        }
        
        response = requests.get(
            f"https://api.myponto.com/accounts/{account_id}/transactions",
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get transactions: {response.status_code} {response.text}")
        
        data = response.json()
        print(f"Transactions for account {account_id}:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as error:
        print(f"Error getting transactions: {error}")
        raise

def get_account_id(bank_details, iban):
    """Get account ID from bank details using IBAN"""
    print(f"Finding account ID for IBAN {iban}...")
    try:
        for account in bank_details.get("data", []):
            if account.get("attributes", {}).get("reference") == iban:
                print(f"Found account ID: {account.get('id')}")
                return account.get("id")
        raise ValueError(f"No account found with IBAN {iban}")
    except Exception as error:
        print(f"Error finding account ID: {error}")
        raise

def main():
    """Main function"""
    try:
        access_token = get_access_token()
        if (access_token):
        
            bank_detail = get_bank_account_details(access_token)
        
            bank_id = os.getenv("BANK_ACCOUNT_IBAN")
            account_id = get_account_id(bank_detail, bank_id)
        
            transactions = get_account_transactions(access_token, account_id)
        
        print("Bank watch completed successfully")
    except Exception as error:
        print(f"Error in bank watch: {error}")


if __name__ == "__main__":
    main()
